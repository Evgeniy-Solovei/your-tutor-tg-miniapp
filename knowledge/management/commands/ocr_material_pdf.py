"""
OCR PDF → текстовый файл в materials/.../_ocr_text/ (или --out).

  ./venv/bin/python manage.py ocr_material_pdf \\
    materials/russian/11_klass/variants/ce/CE_rus_2023_scan.pdf \\
    --dpi 200 --lang rus

Пишет PNG во workspace (materials/_ocr_tmp/), не в /tmp — tesseract так надёжнее.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'OCR PDF через pdftoppm + tesseract (rus)'

    def add_arguments(self, parser):
        parser.add_argument('pdf', type=str)
        parser.add_argument('--out', type=str, default='')
        parser.add_argument('--dpi', type=int, default=200)
        parser.add_argument('--lang', type=str, default='rus')
        parser.add_argument('--pages', type=str, default='', help='напр. 1-5 или 22')
        parser.add_argument('--keep-images', action='store_true')

    def handle(self, *args, **options):
        pdf = Path(options['pdf']).resolve()
        if not pdf.exists():
            self.stderr.write(f'Нет файла: {pdf}')
            return

        if options['out']:
            out = Path(options['out'])
        else:
            out_dir = pdf.parent / '_ocr_text'
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f'{pdf.stem}_OCR.txt'

        work = Path('materials/_ocr_tmp') / pdf.stem
        if options['pages']:
            work = Path('materials/_ocr_tmp') / f'{pdf.stem}_p{options["pages"].replace("-", "_")}'
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)

        prefix = work / 'page'
        cmd = ['pdftoppm', '-png', '-r', str(options['dpi'])]
        if options['pages']:
            p = options['pages']
            if '-' in p:
                a, b = p.split('-', 1)
                cmd += ['-f', a, '-l', b]
            else:
                cmd += ['-f', p, '-l', p]
        cmd += [str(pdf), str(prefix)]
        self.stdout.write(' '.join(cmd))
        subprocess.run(cmd, check=True)

        images = sorted(work.glob('page-*.png'))
        if not images:
            self.stderr.write('Нет страниц после pdftoppm')
            return

        parts: list[str] = []
        for img in images:
            num = int(img.stem.split('-')[-1])
            self.stdout.write(f'OCR page {num}…')
            r = subprocess.run(
                [
                    'tesseract',
                    str(img),
                    'stdout',
                    '-l',
                    options['lang'],
                    '--psm',
                    '6',
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode != 0:
                self.stderr.write(r.stderr[:500])
            parts.append(f'===== PAGE {num} =====\n{(r.stdout or "").rstrip()}\n')

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('\n'.join(parts), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Записано: {out} ({len(images)} стр.)'))

        if not options['keep_images']:
            shutil.rmtree(work, ignore_errors=True)
