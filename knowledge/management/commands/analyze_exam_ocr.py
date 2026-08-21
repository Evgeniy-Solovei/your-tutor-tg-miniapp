"""
Анализ OCR yearbook: карта вариантов + страница ответов.

  ./venv/bin/python manage.py analyze_exam_ocr materials/.../CT_rus_2020_OCR.txt
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Анализ OCR: варианты, страницы А1, ответы'

    def add_arguments(self, parser):
        parser.add_argument('ocr_txt')
        parser.add_argument('--json-out', default='')

    def handle(self, *args, **options):
        path = Path(options['ocr_txt'])
        text = path.read_text(encoding='utf-8')
        pages: dict[int, str] = {}
        parts = re.split(r'===== PAGE (\d+) =====\n?', text)
        it = iter(parts[1:])
        for num, content in zip(it, it):
            pages[int(num)] = content

        a1_pages = sorted(
            p
            for p, c in pages.items()
            if re.search(r'(?:ВАРИАНТ\s*\d+[^\n]{0,40})?А1\.\s*Пишется', c)
            or re.search(r'Часть А[^\n]{0,40}А1\.', c)
            or (re.search(r'(?:^|\n)\s*А1\.\s*', c) and 'Пишется' in c[:800])
        )
        # fallback: any А1.
        if len(a1_pages) < 3:
            a1_pages = sorted(
                p for p, c in pages.items() if re.search(r'(?:^|\n)\s*А1\.\s*', c)
            )

        answer_pages = sorted(
            p for p, c in pages.items() if re.search(r'(?m)^Ответы\b|^ОТВЕТЫ\b', c[:400])
            or (c.lstrip().startswith('Ответы') or 'Ответы' in c[:150] and 'Вариант' in c[:800])
        )

        # Infer variant page ranges: from each A1 page to next A1-1 (or answer-1)
        page_map: dict[int, list[int]] = {}
        ends = a1_pages[1:] + ([answer_pages[0]] if answer_pages else [max(pages) + 1])
        for i, start in enumerate(a1_pages):
            end = ends[i] - 1 if i < len(ends) else max(pages)
            if answer_pages and end >= answer_pages[0]:
                end = answer_pages[0] - 1
            page_map[i + 1] = [start, end]

        report = {
            'file': str(path),
            'pages_total': len(pages),
            'a1_pages': a1_pages,
            'answer_pages': answer_pages,
            'page_map': {str(k): v for k, v in page_map.items()},
            'variants_guess': len(a1_pages),
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if options['json_out']:
            Path(options['json_out']).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
            )
