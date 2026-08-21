"""
Регистрирует PDF-сборники ЦТ/ЦЭ/РТ/ДРТ в ExamCollection (без парсинга заданий).

  python manage.py register_exam_materials
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge.models import ExamCollection, Subject

VARIANTS_ROOT = Path('materials/russian/11_klass/variants')
PRACTICE_ROOT = Path('materials/russian/11_klass/practice')
PREP_ROOT = Path('materials/russian/shared/prep_courses')


class Command(BaseCommand):
    help = 'Записать все найденные сборники ЦТ/ЦЭ/РТ в ExamCollection'

    def handle(self, *args, **options):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'order': 1, 'is_active': True},
        )
        base = Path(settings.BASE_DIR)
        created = updated = 0

        files: list[tuple[Path, str, str, int | None]] = []

        for p in sorted((base / VARIANTS_ROOT).rglob('*.pdf')):
            rel = str(p.relative_to(base))
            name = p.name
            year_m = re.search(r'(20\d{2}|19\d{2})', name)
            year = int(year_m.group(1)) if year_m else None
            if name.startswith('CE_CT_'):
                title = f'ЦЭ/ЦТ русский язык {year or "?"}'
                pub = 'РИКЗ / Аверсэв'
            elif name.startswith('CE_'):
                title = f'ЦЭ русский язык {year or "?"}'
                pub = 'РИКЗ'
            elif name.startswith('CT_sbornik_'):
                title = f'Сборник ЦТ {name.replace("CT_sbornik_TsT_", "").replace("_scan.pdf", "")}'
                pub = 'РИКЗ / сборник тестов'
                year = None
            elif name.startswith('CT_'):
                title = f'ЦТ русский язык {year or "?"}'
                pub = 'РИКЗ'
            else:
                title = name
                pub = ''
            quality = 'scan' if '_scan' in name else ('bad_ocr' if 'bad_encoding' in name else 'text')
            files.append((p, f'{title} [{quality}]', pub, year))

        for folder, label in [
            (PRACTICE_ROOT / 'rt', 'РТ консультация'),
            (PRACTICE_ROOT / 'drt', 'ДРТ консультация'),
            (PRACTICE_ROOT / 'trenazher', 'Тренажёр'),
            (PRACTICE_ROOT / 'tests', 'Тесты'),
            (PREP_ROOT, 'Курс подготовки'),
        ]:
            root = base / folder
            if not root.exists():
                continue
            for p in sorted(root.glob('*')):
                if p.suffix.lower() not in {'.pdf', '.docx'}:
                    continue
                year_m = re.search(r'(20\d{2}|19\d{2})', p.name)
                year = int(year_m.group(1)) if year_m else None
                files.append((p, f'{label}: {p.stem}', '', year))

        for path, title, publisher, year in files:
            rel = str(path.relative_to(base))
            obj, was_created = ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=rel,
                defaults={
                    'title': title[:255],
                    'publisher': publisher[:150],
                    'year': year,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Сборники: создано {created}, обновлено {updated}, всего в БД '
                f'{ExamCollection.objects.count()}'
            )
        )
