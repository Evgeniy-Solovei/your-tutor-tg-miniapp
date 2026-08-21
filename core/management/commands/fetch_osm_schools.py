"""Скачивает школы Беларуси из OpenStreetMap (Overpass) в data/osm_schools.json."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

DATA_DIR = Path(settings.BASE_DIR) / 'data'
ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
]


class Command(BaseCommand):
    help = 'Скачивает школы РБ тайлами через Overpass API'

    def add_arguments(self, parser):
        parser.add_argument('--out', default='osm_schools.json')
        parser.add_argument('--sleep', type=float, default=1.5)

    def handle(self, *args, **options):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = DATA_DIR / options['out']

        lats = [51.25, 52.4, 53.55, 54.7, 55.85, 56.2]
        lons = [23.15, 25.0, 26.85, 28.7, 30.55, 32.75]
        schools: dict[tuple, dict] = {}

        # продолжить с уже скачанного файла
        if out_path.exists():
            try:
                prev = json.loads(out_path.read_text(encoding='utf-8'))
                for el in prev.get('elements') or []:
                    schools[(el.get('type'), el.get('id'))] = el
                self.stdout.write(f'Уже в файле: {len(schools)}')
            except Exception:
                pass

        for i in range(len(lats) - 1):
            for j in range(len(lons) - 1):
                south, west, north, east = lats[i], lons[j], lats[i + 1], lons[j + 1]
                query = f'''[out:json][timeout:120];
(
  node["amenity"="school"]({south},{west},{north},{east});
  way["amenity"="school"]({south},{west},{north},{east});
  node["amenity"="college"]({south},{west},{north},{east});
  way["amenity"="college"]({south},{west},{north},{east});
);
out center tags;'''
                ok = False
                for ep in ENDPOINTS:
                    try:
                        self.stdout.write(
                            f'tile {south:.1f},{west:.1f} via {ep.split("/")[2]}'
                        )
                        payload = self._fetch(ep, query)
                        before = len(schools)
                        for el in payload.get('elements') or []:
                            schools[(el.get('type'), el.get('id'))] = el
                        self.stdout.write(
                            f'  +{len(payload.get("elements") or [])} '
                            f'unique={len(schools)} (Δ{len(schools) - before})'
                        )
                        ok = True
                        time.sleep(options['sleep'])
                        break
                    except Exception as exc:
                        self.stdout.write(f'  fail {exc}')
                        time.sleep(2)
                if not ok:
                    self.stderr.write(f'TILE FAILED {south} {west} {north} {east}')
                # промежуточный сейв
                out_path.write_text(
                    json.dumps({'elements': list(schools.values())}, ensure_ascii=False),
                    encoding='utf-8',
                )

        self.stdout.write(self.style.SUCCESS(f'Сохранено школ: {len(schools)} → {out_path}'))

    def _fetch(self, endpoint: str, query: str, timeout: int = 160) -> dict:
        req = urllib.request.Request(
            endpoint,
            data=query.encode('utf-8'),
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'TutorBotBY/1.0',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'HTTP {exc.code}') from exc
