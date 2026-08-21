"""Импорт городов/НП Беларуси и школ из data/."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import AppSettings, City, School

DATA_DIR = Path(settings.BASE_DIR) / 'data'

# Приблизительный bbox РБ (без глубокого захвата Литвы/Польши)
BY_BBOX = (51.2, 23.15, 56.2, 32.8)


def _norm(value: str) -> str:
    value = (value or '').strip().casefold()
    value = value.replace('ё', 'е').replace('’', "'").replace('ʼ', "'").replace('`', "'")
    value = re.sub(r'\s+', ' ', value)
    return value


def _is_mostly_cyrillic(name: str) -> bool:
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return False
    cyr = sum(1 for c in letters if '\u0400' <= c <= '\u04FF')
    return (cyr / len(letters)) >= 0.75


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _school_coords(el: dict):
    if 'lat' in el and 'lon' in el:
        return float(el['lat']), float(el['lon'])
    center = el.get('center') or {}
    if 'lat' in center and 'lon' in center:
        return float(center['lat']), float(center['lon'])
    return None


def _in_belarus_bbox(lat: float, lon: float) -> bool:
    south, west, north, east = BY_BBOX
    if not (south <= lat <= north and west <= lon <= east):
        return False
    # Литва (Вильнюс/Каунас) — севернее Гродно, западнее Сморгони
    if lat > 54.4 and lon < 24.5:
        return False
    # Польша около Белостока (не трогаем Брест ~52.1, 23.7)
    if lat > 52.6 and lat < 53.9 and lon < 23.55:
        return False
    # РФ у Невеля
    if lon > 31.6 and lat > 55.6:
        return False
    return True


def _school_city_hint(tags: dict) -> str:
    for key in ('addr:city', 'addr:town', 'addr:place', 'is_in:city', 'is_in:town'):
        val = (tags.get(key) or '').strip()
        if val:
            return val
    return ''


def _clean_hint(hint: str) -> str:
    return re.sub(
        r'^(г\.|город|пгт|пос[её]лок|аг\.|агрогородок)\s+',
        '',
        hint.strip(),
        flags=re.I,
    ).strip()


def _school_name(tags: dict) -> str:
    name = (tags.get('name:ru') or tags.get('name') or tags.get('name:be') or '').strip()
    return name[:255] if name else ''


def _country_ok(tags: dict) -> bool:
    country = (
        tags.get('addr:country')
        or tags.get('is_in:country_code')
        or tags.get('is_in:country')
        or ''
    ).strip()
    if not country:
        return True
    c = country.casefold()
    return c in {'by', 'belarus', 'беларусь', 'белоруссия', 'republic of belarus'}


class Command(BaseCommand):
    help = 'Импортирует города Беларуси и школы (OSM) из data/'

    def add_arguments(self, parser):
        parser.add_argument('--clear-schools', action='store_true')
        parser.add_argument(
            '--prune-foreign',
            action='store_true',
            help='Удалить города не из списка settlements и не на кириллице',
        )
        parser.add_argument('--schools-file', default='osm_schools.json')
        parser.add_argument('--settlements-file', default='belarus_settlements.json')

    def handle(self, *args, **options):
        settlements_path = DATA_DIR / options['settlements_file']
        schools_path = DATA_DIR / options['schools_file']

        if not settlements_path.exists():
            self.stderr.write(f'Нет файла {settlements_path}')
            return

        AppSettings.objects.get_or_create(pk=1)
        settlements = json.loads(settlements_path.read_text(encoding='utf-8'))
        whitelist_norms = {_norm(s['name']) for s in settlements if s.get('name')}

        city_by_norm: dict[str, City] = {}
        created_cities = 0
        with transaction.atomic():
            for item in settlements:
                name = (item.get('name') or '').strip()
                if not name:
                    continue
                region = (item.get('region') or '')[:100]
                city, created = City.objects.get_or_create(
                    name=name,
                    defaults={'region': region, 'is_active': True},
                )
                if created:
                    created_cities += 1
                elif region and not city.region:
                    city.region = region
                    city.save(update_fields=['region'])
                city_by_norm[_norm(name)] = city

        if options['prune_foreign']:
            removed = 0
            for city in City.objects.all():
                n = _norm(city.name)
                if n in whitelist_norms or _is_mostly_cyrillic(city.name):
                    continue
                city.delete()
                removed += 1
            self.stdout.write(f'Удалено иностранных городов: {removed}')
            # обновить словарь
            city_by_norm = {_norm(c.name): c for c in City.objects.all()}

        self.stdout.write(self.style.SUCCESS(
            f'Городов/НП: создано {created_cities}, всего {City.objects.count()}'
        ))

        if not schools_path.exists():
            self.stdout.write(self.style.WARNING(
                f'Нет {schools_path} — школы пропущены. '
                f'Сначала: python manage.py fetch_osm_schools'
            ))
            return

        if options['clear_schools']:
            deleted, _ = School.objects.all().delete()
            self.stdout.write(f'Школ удалено: {deleted}')

        payload = json.loads(schools_path.read_text(encoding='utf-8'))
        elements = payload.get('elements') or payload

        city_coords: list[tuple[City, float, float, int]] = []
        for item in settlements:
            name = (item.get('name') or '').strip()
            if not name or 'lat' not in item:
                continue
            city = city_by_norm.get(_norm(name))
            if city:
                city_coords.append((
                    city,
                    float(item['lat']),
                    float(item['lon']),
                    int(item.get('population') or 0),
                ))

        created_schools = 0
        skipped = 0
        created_from_addr = 0

        with transaction.atomic():
            for el in elements:
                tags = el.get('tags') or {}
                if not _country_ok(tags):
                    skipped += 1
                    continue

                coords = _school_coords(el)
                if coords and not _in_belarus_bbox(*coords):
                    skipped += 1
                    continue

                name = _school_name(tags)
                if not name:
                    skipped += 1
                    continue

                city = None
                hint = _clean_hint(_school_city_hint(tags))
                if hint:
                    city = city_by_norm.get(_norm(hint))

                if city is None and coords and city_coords:
                    # среди ближайших НП предпочитаем крупный город
                    # (иначе школы Минска «прилипают» к Сеннице/Ждановичам)
                    lat, lon = coords
                    scored = []
                    for c, clat, clon, pop in city_coords:
                        d = _haversine_km(lat, lon, clat, clon)
                        if d > 40:
                            continue
                        # чем больше население — тем шире «зона притяжения»
                        score = d / math.log10(max(pop, 10) + 10)
                        scored.append((score, d, -pop, c))
                    if scored:
                        scored.sort()
                        city = scored[0][3]

                if city is None and hint and _is_mostly_cyrillic(hint) and coords:
                    # локальный посёлок/деревня внутри РБ
                    city, made = City.objects.get_or_create(
                        name=hint[:100],
                        defaults={'region': '', 'is_active': True},
                    )
                    city_by_norm[_norm(hint)] = city
                    if made:
                        created_from_addr += 1

                if city is None:
                    skipped += 1
                    continue

                _, created = School.objects.get_or_create(
                    city=city,
                    name=name,
                    defaults={'is_active': True},
                )
                if created:
                    created_schools += 1

        self.stdout.write(self.style.SUCCESS(
            f'Школ создано: {created_schools}, всего: {School.objects.count()}, '
            f'пропущено: {skipped}, новых НП из адресов: {created_from_addr}'
        ))
