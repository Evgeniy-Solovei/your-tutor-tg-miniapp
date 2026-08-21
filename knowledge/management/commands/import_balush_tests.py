"""
Импорт тематических тестов Балуш (ч.1/ч.2 задания + ч.3 ключи).

  ./venv/bin/python manage.py import_balush_tests --theme fonetika
  ./venv/bin/python manage.py import_balush_tests --chapter 2 --theme morfologiya
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
CHAPTER_PDF = {
    1: (
        'materials/russian/shared/prep_courses/'
        'Balush_prakticheskiy_kurs_CT_ch1_scan_NO_TEXT.pdf'
    ),
    2: (
        'materials/russian/shared/prep_courses/'
        'Balush_prakticheskiy_kurs_CT_ch2_scan_NO_TEXT.pdf'
    ),
}


class Command(BaseCommand):
    help = 'Импорт тестов Балуш ч.1/ч.2 (JSON заданий + KEYS)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--theme',
            default='fonetika',
            help='slug темы: fonetika, leksika, morfemika, pravopisanie, morfologiya…',
        )
        parser.add_argument('--chapter', type=int, default=1, choices=[1, 2])
        parser.add_argument('--clear', action='store_true')
        parser.add_argument('--dir', default=str(DEFAULT_DIR))

    def handle(self, *args, **options):
        base = Path(options['dir'])
        if not base.is_absolute():
            base = Path(settings.BASE_DIR) / base
        chapter = options['chapter']
        theme = options['theme']
        source_prefix = f'Балуш ч.{chapter}'
        tasks_path = base / f'Balush_ch{chapter}_{theme}_TASKS.json'
        keys_path = base / f'Balush_ch{chapter}_{theme}_KEYS.json'
        if not tasks_path.exists() or not keys_path.exists():
            self.stderr.write(self.style.ERROR(f'Нет {tasks_path.name} / {keys_path.name}'))
            return

        tasks_data = json.loads(tasks_path.read_text(encoding='utf-8'))
        keys_data = json.loads(keys_path.read_text(encoding='utf-8'))
        answers = {str(k): str(v).replace(' ', '') for k, v in keys_data['answers'].items()}
        theme_name = tasks_data.get('theme') or keys_data.get('theme') or theme

        with transaction.atomic():
            subject, track, version = self._ensure_structure()
            section, _ = Section.objects.get_or_create(
                exam_track=track,
                content_version=version,
                name=f'Балуш — практический курс ЦТ (ч.{chapter})',
                defaults={'order': 15 + chapter},
            )
            if options['clear']:
                deleted, _ = Task.objects.filter(
                    source__startswith=f'{source_prefix} / {theme_name}'
                ).delete()
                self.stdout.write(f'Удалено: {deleted}')

            topic, _ = Topic.objects.get_or_create(
                section=section,
                name=theme_name[:200],
                defaults={
                    'grade_level': 11,
                    'exam_weight': 1.0,
                    'order': 1,
                    'is_active': True,
                },
            )
            TopicSummary.objects.update_or_create(
                topic=topic,
                defaults={
                    'title': f'Балуш ч.{chapter} — {theme_name}',
                    'content': (
                        'Тестовые задания из «Практический курс эффективной '
                        f'подготовки к ЦТ» (Балуш Т.В., ч.{chapter}). Ключи — из ч.3.'
                    ),
                    'key_points': 'Мультивыбор как на ЦТ; соответствие — текстовый ответ.',
                    'source_note': 'Балуш Т.В., Выснова / готовимся к экзамену',
                },
            )

            created = 0
            for item in tasks_data['tasks']:
                num = int(item['num'])
                ans = answers.get(str(num))
                if not ans:
                    self.stderr.write(f'Нет ключа для №{num}')
                    continue
                source = f'{source_prefix} / {theme_name} / Т{num}'
                if Task.objects.filter(source=source).exists():
                    continue

                qtype = item.get('type', 'mc')
                stem = item['stem'].strip()
                opts = item.get('options') or []
                question = f'[Балуш ч.{chapter} · {theme_name} · Т{num}] {stem}'

                if qtype == 'match' or not opts:
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
                    explanation=f'Ключ Балуш ч.3, тема «{theme_name}», Т{num}: {ans}',
                    common_mistakes='',
                )
                created += 1

            pdf_rel = CHAPTER_PDF[chapter]
            ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=pdf_rel,
                defaults={
                    'title': f'Балуш — Практический курс подготовки к ЦТ, часть {chapter}',
                    'publisher': 'Выснова',
                    'year': 2017 if chapter == 2 else 2018,
                    'is_active': True,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'Импортировано: {created} ({theme_name})'))

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
