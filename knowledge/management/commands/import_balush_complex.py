"""
Импорт комплексных тестов Балуш (ч.2 варианты + ч.3 ключи).

  ./venv/bin/python manage.py import_balush_complex --variant 1
  ./venv/bin/python manage.py import_balush_complex --variant 1 --clear
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import (
    ContentVersion,
    ExamCollection,
    ExamTrack,
    Section,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    Topic,
    TopicSummary,
)

DEFAULT_DIR = Path('materials/russian/shared/prep_courses/_ocr_text')
CHAPTER_PDF = (
    'materials/russian/shared/prep_courses/'
    'Balush_prakticheskiy_kurs_CT_ch2_scan_NO_TEXT.pdf'
)

READING_CODES = frozenset(f'A{n}' for n in range(30, 33)) | frozenset(
    f'B{n}' for n in range(1, 6)
)


class Command(BaseCommand):
    help = 'Импорт комплексных тестов Балуш ч.2 (JSON заданий + KEYS)'

    def add_arguments(self, parser):
        parser.add_argument('--variant', type=int, required=True, help='номер варианта 1–5')
        parser.add_argument('--clear', action='store_true')
        parser.add_argument('--dir', default=str(DEFAULT_DIR))

    def handle(self, *args, **options):
        variant = options['variant']
        base = Path(options['dir'])
        if not base.is_absolute():
            base = Path(settings.BASE_DIR) / base

        tasks_path = base / f'Balush_ch2_complex_v{variant}_TASKS.json'
        keys_path = base / f'Balush_ch2_complex_v{variant}_KEYS.json'
        if not tasks_path.exists() or not keys_path.exists():
            self.stderr.write(
                self.style.ERROR(f'Нет {tasks_path.name} / {keys_path.name}')
            )
            return

        tasks_data = json.loads(tasks_path.read_text(encoding='utf-8'))
        keys_data = json.loads(keys_path.read_text(encoding='utf-8'))
        answers = {
            k.upper().replace('A', 'А').replace('B', 'В'): str(v).replace(' ', '')
            for k, v in keys_data['answers'].items()
        }
        scores = keys_data.get('scores') or {}
        reading = (tasks_data.get('reading_text') or '').strip()
        title = tasks_data.get('title') or f'Комплексный тест, вариант {variant}'

        with transaction.atomic():
            subject, track, version = self._ensure_structure()
            section, _ = Section.objects.get_or_create(
                exam_track=track,
                content_version=version,
                name='Балуш — практический курс ЦТ (ч.2)',
                defaults={'order': 17},
            )
            source_prefix = f'Балуш ч.2 / {title}'
            if options['clear']:
                deleted, _ = Task.objects.filter(
                    source__startswith=source_prefix
                ).delete()
                self.stdout.write(f'Удалено: {deleted}')

            topic, _ = Topic.objects.get_or_create(
                section=section,
                name=title[:200],
                defaults={
                    'grade_level': 11,
                    'exam_weight': 1.0,
                    'order': 100 + variant,
                    'is_active': True,
                },
            )
            TopicSummary.objects.update_or_create(
                topic=topic,
                defaults={
                    'title': title,
                    'content': (
                        'Комплексный тест из «Практический курс эффективной '
                        'подготовки к ЦТ» (Балуш Т.В., ч.2). Ключи — из ч.3.'
                    ),
                    'key_points': 'Часть А — мультивыбор; часть B — текст и соответствие.',
                    'source_note': 'Балуш Т.В., Выснова / готовимся к экзамену',
                },
            )

            created = 0
            for item in tasks_data['tasks']:
                code = item['code'].upper().replace('A', 'А').replace('B', 'В')
                ans = answers.get(code)
                if not ans:
                    self.stderr.write(f'Нет ключа для {code}')
                    continue
                source = f'{source_prefix} / {code}'
                if Task.objects.filter(source=source).exists():
                    continue

                qtype = item.get('type', 'mc')
                stem = item['stem'].strip()
                opts = item.get('options') or []
                if reading and (item.get('uses_reading_text') or code in READING_CODES):
                    stem = f'Текст:\n{reading}\n\n{stem}'

                question = f'[Балуш ч.2 · {title} · {code}] {stem}'
                score_note = scores.get(code) or scores.get(code.replace('А', 'A').replace('В', 'B'))
                score_suffix = f' (макс. {score_note} б.)' if score_note else ''

                if qtype == 'match' or (qtype != 'mc' and not opts):
                    fmt = Task.AnswerFormat.TEXT
                    scheme = Task.ScoringScheme.BINARY_2
                else:
                    fmt = Task.AnswerFormat.MULTIPLE_CHOICE
                    scheme = Task.ScoringScheme.PARTIAL_2

                task = Task.objects.create(
                    topic=topic,
                    question=question[:4000],
                    answer_format=fmt,
                    difficulty=Task.Difficulty.MEDIUM,
                    source=source,
                    is_active=True,
                    scoring_scheme=scheme,
                )
                if fmt == Task.AnswerFormat.MULTIPLE_CHOICE:
                    correct = {
                        int(x) for x in ans.split(',') if x.strip().isdigit()
                    }
                    for idx, label in enumerate(opts, start=1):
                        TaskOption.objects.create(
                            task=task,
                            text=f'{idx}) {label}'[:500],
                            is_correct=idx in correct,
                            order=idx,
                        )
                TaskSolution.objects.create(
                    task=task,
                    correct_answer=ans,
                    explanation=(
                        f'Ключ Балуш ч.3, {title}, {code}: {ans}{score_suffix}'
                    ),
                    common_mistakes='',
                )
                created += 1

            ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=CHAPTER_PDF,
                defaults={
                    'title': 'Балуш — Практический курс подготовки к ЦТ, часть 2',
                    'publisher': 'Выснова',
                    'year': 2017,
                    'is_active': True,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'Импортировано: {created} ({title})'))

    def _ensure_structure(self):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'order': 1, 'is_active': True},
        )
        track, _ = ExamTrack.objects.get_or_create(
            subject=subject,
            track_type=ExamTrack.TrackType.CT_11,
            defaults={
                'name': 'ЦТ по русскому языку (после 11 класса)',
                'grade_from': 10,
                'grade_to': 11,
                'is_active': True,
            },
        )
        version, _ = ContentVersion.objects.update_or_create(
            subject=subject,
            year=2018,
            defaults={
                'title': 'Балуш практический курс ЦТ',
                'is_current': False,
                'notes': 'prep_courses/Balush',
            },
        )
        return subject, track, version
