"""
Импорт ЦТ/ЦЭ из OCR-текста + JSON-ключей (vision/таблица ответов).

  ./venv/bin/python manage.py import_ct_ocr_year --exam ct --year 2023
  ./venv/bin/python manage.py import_ct_ocr_year --exam ce --year 2023
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import (
    ContentVersion,
    ExamCollection,
    ExamTrack,
    ExamVariant,
    Section,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    Topic,
    TopicSummary,
    VariantTask,
)
from knowledge.pdf_parser import extract_numbered_options

# exam → year → {variant: (page_from, page_to)}
PAGE_MAPS = {
    'ct': {
        2023: {
            1: (2, 5),
            2: (6, 9),
            3: (10, 13),
            4: (14, 17),
            5: (18, 21),
        },
        2020: {
            1: (4, 8),
            2: (9, 13),
            3: (14, 18),
            4: (19, 23),
            5: (24, 28),
            6: (29, 33),
            7: (34, 38),
            8: (39, 43),
            9: (44, 48),
            10: (49, 53),
        },
        2019: {
            1: (2, 5),
            2: (6, 9),
            3: (10, 13),
            4: (14, 17),
            5: (18, 21),
            6: (22, 25),
            7: (26, 29),
            8: (30, 33),
            9: (34, 37),
            10: (38, 41),
        },
        2021: {
            1: (4, 7),
            2: (8, 11),
            3: (12, 15),
            4: (16, 19),
            5: (20, 23),
            6: (24, 27),
            7: (28, 31),
            8: (32, 35),
            9: (36, 39),
            10: (40, 43),
        },
        2022: {
            1: (2, 6),
            2: (7, 11),
            3: (12, 16),
            4: (17, 21),
            5: (22, 26),
            6: (27, 31),
            7: (32, 36),
            8: (37, 41),
            9: (42, 46),
            10: (47, 51),
        },
        2018: {
            1: (2, 6),
            2: (7, 11),
            3: (12, 16),
            4: (17, 21),
            5: (22, 26),
            6: (27, 31),
            7: (32, 36),
            8: (37, 41),
            9: (42, 46),
            10: (47, 51),
        },
        2016: {
            1: (2, 5),
            2: (6, 9),
            3: (10, 13),
            4: (14, 17),
            5: (18, 21),
            6: (22, 25),
            7: (26, 29),
            8: (30, 33),
            9: (34, 37),
            10: (38, 41),
        },
        2015: {
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2010: {
            # CT_rus_2010_scan_weak.pdf; А1–А32 / В1–В8; ответы 41–42
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2011: {
            # collections/CT_sbornik_TsT_2011-2012; А1–А32 / В1–В8; ответы 41–42
            # (2010-2011 sbornik = дубль ЦТ 2010, не использовать)
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2012: {
            # collections/CT_sbornik_TsT_2012-2013; А1–А32 / В1–В8; ответы 41–42
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2013: {
            # collections/CT_sbornik_TsT_2013-2014 (== archived CT_rus_2013); А1–А32 / В1–В8; ответы 41–42
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2014: {
            # collections/CT_sbornik_TsT_2014-2015; А1–А32 / В1–В8; ответы 41–42 (2015 уже в БД)
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2017: {
            # CT_rus_2017_text_KEYS_OCR_BAD.pdf; формат А1–А30 / В1–В10; ответы 41–42
            1: (1, 4),
            2: (5, 8),
            3: (9, 12),
            4: (13, 16),
            5: (17, 20),
            6: (21, 24),
            7: (25, 28),
            8: (29, 32),
            9: (33, 36),
            10: (37, 40),
        },
        2005: {
            # из collections/CT_sbornik_TsT_2005-2006; формат А1–А30 / В1–В10; ответы 57–58
            1: (1, 6),
            2: (7, 11),
            3: (12, 17),
            4: (18, 22),
            5: (23, 28),
            6: (29, 33),
            7: (34, 39),
            8: (40, 44),
            9: (45, 50),
            10: (51, 56),
        },
        2006: {
            # collections/CT_sbornik_TsT_2006-2007; А1–А32 / В1–В8; ответы 52–53
            1: (1, 5),
            2: (6, 10),
            3: (11, 15),
            4: (16, 20),
            5: (21, 25),
            6: (26, 30),
            7: (31, 35),
            8: (36, 40),
            9: (41, 45),
            10: (46, 51),
        },
        2007: {
            # collections/CT_sbornik_TsT_2007-2008; А1–А32 / В1–В8; ответы 52–54
            1: (1, 5),
            2: (6, 10),
            3: (11, 15),
            4: (16, 20),
            5: (21, 25),
            6: (26, 30),
            7: (31, 35),
            8: (36, 40),
            9: (41, 45),
            10: (46, 51),
        },
        2009: {
            # формат А1–А32 / В1–В8; границы вариантов на стыке страниц
            1: (1, 5),
            2: (6, 10),
            3: (11, 15),
            4: (16, 20),
            5: (21, 25),
            6: (26, 30),
            7: (31, 35),
            8: (36, 40),
            9: (41, 45),
            10: (46, 51),
        },
        2008: {
            1: (1, 5),
            2: (6, 10),
            3: (11, 15),
            4: (16, 20),
            5: (21, 25),
            6: (26, 30),
            7: (31, 35),
            8: (36, 40),
            9: (41, 45),
            10: (46, 51),
        },
        2004: {
            # B3–B8 вар.1 на PDF p5 (левая половина разворота с ТЕСТ 2).
            1: (1, 5),
            2: (5, 9),
            3: (10, 14),
            4: (14, 18),
            5: (19, 23),
            6: (23, 27),
            7: (28, 32),
            8: (32, 37),
            9: (37, 41),
            10: (42, 46),
        },
        2003: {
            # А1–А40, без В; книга «с ответами и комментариями» —
            # на развороте тест + комментарий; вар.1 реально PDF p1–8 (А40 на p8).
            # Равномерная нарезка ниже — legacy; для качества → update_ct_vision_tasks.
            1: (1, 8),
            2: (9, 14),
            3: (15, 20),
            4: (20, 25),
            5: (26, 31),
            6: (31, 36),
            7: (37, 41),
            8: (42, 47),
            9: (47, 52),
            10: (53, 58),
        },
    },
    'ce': {
        2023: {
            1: (3, 6),
            2: (7, 10),
            3: (11, 14),
            4: (15, 18),
            5: (19, 22),
        }
    },
    'ce_ct': {
        # CE_CT_rus_2024_scan.pdf — 5 вариантов + ответы
        2024: {
            1: (3, 7),
            2: (8, 12),
            3: (13, 17),
            4: (18, 22),
            5: (23, 27),
        },
        # CE_CT_rus_2025_scan.pdf
        2025: {
            1: (2, 6),
            2: (7, 11),
            3: (12, 16),
            4: (17, 21),
            5: (22, 26),
        },
    },
}

EXAM_META = {
    'ct': {
        'label': 'ЦТ',
        'source_prefix': 'ЦТ OCR',
        'ocr_dir': Path('materials/russian/11_klass/variants/_ocr_text'),
        'file_stem': 'CT_rus_{year}',
        'pdf_rel': 'materials/russian/11_klass/variants/ct/CT_rus_{year}_scan.pdf',
        'track_type': ExamTrack.TrackType.CT_11,
        'track_name': 'ЦТ по русскому языку (после 11 класса)',
        'section_order': 30,
    },
    'ce': {
        'label': 'ЦЭ',
        'source_prefix': 'ЦЭ OCR',
        'ocr_dir': Path('materials/russian/11_klass/variants/ce/_ocr_text'),
        'file_stem': 'CE_rus_{year}',
        'pdf_rel': 'materials/russian/11_klass/variants/ce/CE_rus_{year}_scan.pdf',
        'track_type': ExamTrack.TrackType.CE_11,
        'track_name': 'ЦЭ по русскому языку (после 11 класса)',
        'section_order': 31,
    },
    'ce_ct': {
        'label': 'ЦЭ/ЦТ',
        'source_prefix': 'ЦЭ/ЦТ OCR',
        'ocr_dir': Path('materials/russian/11_klass/variants/ce_ct/_ocr_text'),
        'file_stem': 'CE_CT_rus_{year}',
        'pdf_rel': 'materials/russian/11_klass/variants/ce_ct/CE_CT_rus_{year}_scan.pdf',
        'track_type': ExamTrack.TrackType.CE_11,
        'track_name': 'ЦЭ по русскому языку (после 11 класса)',
        'section_order': 32,
    },
}


def _load_pages(ocr_txt: Path) -> dict[int, str]:
    text = ocr_txt.read_text(encoding='utf-8')
    pages: dict[int, str] = {}
    parts = re.split(r'===== PAGE (\d+) =====\n?', text)
    it = iter(parts[1:])
    for num, content in zip(it, it):
        pages[int(num)] = content
    return pages


def _parse_tasks_from_block(block: str) -> dict[str, tuple[str, list[str]]]:
    """Достаёт А1.. / В1.. из OCR-блока варианта."""
    block = re.sub(r'(?i)\bA(\d+)\.', r'А\1.', block)
    block = re.sub(r'(?i)\bB(\d+)\.', r'В\1.', block)
    block = re.sub(r'Ал\.', 'А1.', block)
    block = re.sub(r'Ал\.', 'А1.', block)
    # типичный мусор маркеров в ЦЭ/ЦТ сканах
    block = re.sub(r"(?m)^[''`‚,]?\s*ВА\.\s*", 'В4. ', block)
    block = re.sub(r"(?m)^[''`‚,]?\s*А\$\.\s*", 'А3. ', block)
    block = re.sub(r"(?m)^[''`‚,]?\s*А\.\s*(?=Двойные)", 'А3. ', block)
    block = re.sub(r'В6б\.', 'В6.', block)
    block = re.sub(r'В135\.', 'В13.', block)
    block = re.sub(r'В1\.4\.', 'В14.', block)
    block = re.sub(r'(?m)^В\.\s*(?=В слове, выделенном)', 'В3. ', block)
    # В3 часто распознаётся как первое «В5.» после В2
    block = re.sub(
        r'(В2\..*?\n)В5\.(\s*В слове, выделенном)',
        r'\1В3.\2',
        block,
        count=1,
        flags=re.S,
    )
    # А3 «Двойные согласные» иногда помечено как А5
    block = re.sub(
        r'(А2\..*?\n)А5\.(\s*Двойные согласные)',
        r'\1А3.\2',
        block,
        count=1,
        flags=re.S,
    )

    def _fix_marker_digits(m: re.Match) -> str:
        digits = (
            m.group(2)
            .replace('З', '3')
            .replace('з', '3')
            .replace('О', '0')
            .replace('о', '0')
            .replace('Б', '6')
            .replace('б', '6')
        )
        letter = m.group(1).upper().replace('A', 'А').replace('B', 'В')
        return f'{letter}{digits}.'

    block = re.sub(r'([АAВB])\s*([0-9ЗзОоБб]{1,2})\.', _fix_marker_digits, block)
    out: dict[str, tuple[str, list[str]]] = {}
    matches = list(re.finditer(r'(?:^|[\n\r])[^\nАAВB]{0,6}([АAВB])\s*(\d+)\.\s*', block))
    for i, m in enumerate(matches):
        letter = m.group(1).upper().replace('A', 'А').replace('B', 'В')
        num = int(m.group(2))
        if letter == 'А' and not (1 <= num <= 40):
            continue
        if letter == 'В' and not (1 <= num <= 22):
            continue
        code = f'{letter}{num}'
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        body = block[start:end].strip()
        body = re.split(r'\n(?:Ответы|ВАРИАНТ\s*\d+)', body)[0].strip()
        opts = extract_numbered_options(body)
        if len(opts) < 2:
            opts = []
            for om in re.finditer(
                r'(?:^|\n)\s*(\d)\)\s*([^\n]+(?:\n(?!\s*\d\))[^\n]+)*)',
                body,
            ):
                opts.append(re.sub(r'\s+', ' ', om.group(2)).strip().rstrip(';.,')[:490])
        stem = re.split(r'\n\s*\d\)', body, maxsplit=1)[0]
        stem = re.sub(r'\s+', ' ', stem).strip()
        stem = stem.replace(' Ha ', ' на ').replace(' COOTBETCTBYIOT ', ' соответствуют ')
        if len(stem) < 8 and not opts:
            continue
        out[code] = (stem[:2000], opts)
    return out


class Command(BaseCommand):
    help = 'Импорт ЦТ/ЦЭ из OCR + JSON-ключей'

    def add_arguments(self, parser):
        parser.add_argument('--exam', choices=['ct', 'ce', 'ce_ct'], default='ct')
        parser.add_argument('--year', type=int, default=2023)
        parser.add_argument('--clear', action='store_true')
        parser.add_argument(
            '--fill-missing',
            action='store_true',
            help='Создавать задания с заглушкой условия, если OCR не вытащил текст, но ключ есть',
        )

    def handle(self, *args, **options):
        exam = options['exam']
        year = options['year']
        meta = EXAM_META[exam]
        page_maps = PAGE_MAPS.get(exam, {})
        if year not in page_maps:
            self.stderr.write(f'Нет карты страниц для {exam.upper()} {year}: {list(page_maps)}')
            return

        file_stem = meta['file_stem'].format(year=year)
        ocr_txt = meta['ocr_dir'] / f'{file_stem}_OCR.txt'
        keys_json = meta['ocr_dir'] / f'{file_stem}_KEYS.json'
        if not ocr_txt.exists() or not keys_json.exists():
            self.stderr.write(f'Нужны {ocr_txt} и {keys_json}')
            return

        pages = _load_pages(ocr_txt)
        keys = json.loads(keys_json.read_text(encoding='utf-8'))
        page_map = page_maps[year]
        label = meta['label']

        with transaction.atomic():
            subject, track, version = self._ensure(year, meta)
            prefix = f'{meta["source_prefix"]} / {label} {year}'
            if options['clear']:
                deleted, _ = Task.objects.filter(source__startswith=prefix).delete()
                self.stdout.write(f'Удалено: {deleted}')

            section, _ = Section.objects.get_or_create(
                exam_track=track,
                content_version=version,
                name=f'{label} {year} (OCR)',
                defaults={'order': meta['section_order']},
            )
            collection, _ = ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=meta['pdf_rel'].format(year=year),
                defaults={
                    'title': f'{label} русский язык {year} (OCR)',
                    'publisher': 'РИКЗ',
                    'year': year,
                    'is_active': True,
                },
            )

            total = 0
            for vnum, (p_from, p_to) in page_map.items():
                block = '\n'.join(pages.get(p, '') for p in range(p_from, p_to + 1))
                parsed = _parse_tasks_from_block(block)
                vkeys = keys.get(str(vnum)) or keys.get(vnum) or {}
                topic, _ = Topic.objects.get_or_create(
                    section=section,
                    name=f'Вариант {vnum}',
                    defaults={
                        'grade_level': 11,
                        'exam_weight': 1.0,
                        'order': vnum,
                        'is_active': True,
                    },
                )
                TopicSummary.objects.update_or_create(
                    topic=topic,
                    defaults={
                        'title': f'{label} {year}, вариант {vnum}',
                        'content': f'Официальный вариант {label} {year} (распознан OCR).',
                        'key_points': 'Ключи с таблицы ответов сборника.',
                        'source_note': f'{file_stem}_scan.pdf + OCR',
                    },
                )
                variant, _ = ExamVariant.objects.update_or_create(
                    collection=collection,
                    number=vnum,
                    defaults={'title': f'Вариант {vnum}', 'year': year, 'is_active': True},
                )

                order = 0
                for code in sorted(
                    vkeys.keys(),
                    key=lambda c: (0 if c.startswith('А') else 1, int(re.sub(r'\D', '', c) or 0)),
                ):
                    answer = vkeys[code]
                    q = parsed.get(code)
                    if not q:
                        if options['fill_missing']:
                            stem_q, opts = (
                                f'(условие не распознано OCR; ключ {label} {year} вар.{vnum} {code})',
                                [],
                            )
                        else:
                            continue
                    else:
                        stem_q, opts = q
                    source = f'{prefix} / вариант {vnum} / {code}'
                    if Task.objects.filter(source=source).exists():
                        continue

                    need_mc = bool(re.fullmatch(r'(?:\d(?:,\d)*)', answer.replace(' ', '')))
                    if need_mc:
                        answer_norm = ','.join(
                            x.strip() for x in answer.replace(' ', '').split(',') if x.strip()
                        )
                    else:
                        answer_norm = answer
                    fmt = (
                        Task.AnswerFormat.MULTIPLE_CHOICE
                        if need_mc and len(opts) >= 2
                        else Task.AnswerFormat.TEXT
                    )
                    if fmt == Task.AnswerFormat.MULTIPLE_CHOICE:
                        max_opt = max(int(x) for x in answer_norm.split(','))
                        while len(opts) < max_opt:
                            opts.append(f'(вариант {len(opts) + 1})')
                        opts = [o[:490] for o in opts]
                    elif opts:
                        stem_q = stem_q + '\n' + '\n'.join(
                            f'{j}) {o}' for j, o in enumerate(opts, 1)
                        )
                        opts = []

                    task = Task.objects.create(
                        topic=topic,
                        question=f'[{label} {year} · вар.{vnum} · {code}] {stem_q}'[:4000],
                        answer_format=fmt,
                        difficulty=Task.Difficulty.MEDIUM,
                        source=source,
                        is_active=True,
                        scoring_scheme=(
                            Task.ScoringScheme.PARTIAL_2
                            if fmt == Task.AnswerFormat.MULTIPLE_CHOICE
                            else Task.ScoringScheme.BINARY_2
                        ),
                    )
                    if fmt == Task.AnswerFormat.MULTIPLE_CHOICE:
                        correct = {int(x) for x in answer_norm.split(',') if x.isdigit()}
                        for idx, label_opt in enumerate(opts, start=1):
                            TaskOption.objects.create(
                                task=task,
                                text=f'{idx}) {label_opt}'[:500],
                                is_correct=idx in correct,
                                order=idx,
                            )
                    TaskSolution.objects.create(
                        task=task,
                        correct_answer=answer_norm,
                        explanation=f'Ключ {label} {year}, вариант {vnum}, {code}: {answer_norm}',
                        common_mistakes='',
                    )
                    order += 1
                    VariantTask.objects.update_or_create(
                        variant=variant,
                        order=order,
                        defaults={'task': task},
                    )
                    total += 1
                miss = sorted(
                    set(vkeys) - set(parsed),
                    key=lambda c: (0 if c.startswith('А') else 1, int(re.sub(r'\D', '', c) or 0)),
                )
                extra = f', нет OCR: {miss}' if miss else ''
                self.stdout.write(
                    f'Вариант {vnum}: OCR {len(parsed)}/{len(vkeys)}, импорт +связан{extra}'
                )

        self.stdout.write(self.style.SUCCESS(f'Импортировано заданий: {total}'))

    def _ensure(self, year: int, meta: dict):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'order': 1, 'is_active': True},
        )
        track, _ = ExamTrack.objects.get_or_create(
            subject=subject,
            track_type=meta['track_type'],
            defaults={
                'name': meta['track_name'],
                'grade_from': 10,
                'grade_to': 11,
                'is_active': True,
            },
        )
        version, _ = ContentVersion.objects.update_or_create(
            subject=subject,
            year=year,
            title=f'{meta["label"]} {year} OCR',
            defaults={
                'is_current': False,
                'notes': f'{meta["label"]} {year}: скан + OCR + ключи таблицы ответов',
            },
        )
        return subject, track, version
