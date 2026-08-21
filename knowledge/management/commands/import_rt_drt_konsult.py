"""
Импорт РТ/ДРТ тематических консультаций (вопрос + Ответ: + разбор).

  python manage.py import_rt_drt_konsult
  python manage.py import_rt_drt_konsult --clear
"""

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
from knowledge.rt_konsult_parser import parse_all_konsult

SOURCE_PREFIX = 'РТ/ДРТ консультация'
DEFAULT_DIRS = [
    'materials/russian/11_klass/practice/rt',
    'materials/russian/11_klass/practice/drt',
]


class Command(BaseCommand):
    help = 'Импорт РТ/ДРТ консультаций с ответами и разбором'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help=f'Удалить задания с source «{SOURCE_PREFIX}»',
        )

    def handle(self, *args, **options):
        dirs = [Path(settings.BASE_DIR) / d for d in DEFAULT_DIRS]
        with transaction.atomic():
            subject, track, version = self._ensure_structure()
            if options['clear']:
                deleted, _ = Task.objects.filter(source__startswith=SOURCE_PREFIX).delete()
                self.stdout.write(f'Удалено: {deleted}')

            banks = parse_all_konsult(dirs)
            total = 0
            for bank in banks:
                section = self._ensure_section(track, version, bank.label)
                topic = self._ensure_topic(section, bank.label)
                created = self._import_tasks(topic, bank)
                total += created
                self.stdout.write(f'{bank.filename}: {len(bank.tasks)} разобрано, +{created} в БД')

            for d in dirs:
                kind = 'РТ' if d.name == 'rt' else 'ДРТ'
                for path in sorted(d.glob('*.pdf')):
                    rel = str(path.relative_to(settings.BASE_DIR))
                    ExamCollection.objects.update_or_create(
                        subject=subject,
                        source_file=rel,
                        defaults={
                            'title': f'{kind}: {path.stem}'[:255],
                            'publisher': 'РИКЗ',
                            'is_active': True,
                        },
                    )

        self.stdout.write(self.style.SUCCESS(f'Готово. Импортировано заданий: {total}'))

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
            year=2024,
            defaults={
                'title': 'РТ/ДРТ тематические консультации РИКЗ',
                'is_current': False,
                'notes': 'practice/rt + practice/drt',
            },
        )
        return subject, track, version

    def _ensure_section(self, track, version, label: str) -> Section:
        section, _ = Section.objects.get_or_create(
            exam_track=track,
            content_version=version,
            name=f'Консультация · {label}'[:200],
            defaults={'order': 20},
        )
        return section

    def _ensure_topic(self, section: Section, label: str) -> Topic:
        topic, _ = Topic.objects.get_or_create(
            section=section,
            name='Задания с разбором',
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
                'title': label,
                'content': f'Тематическое консультирование РИКЗ: {label}',
                'key_points': 'Смотри разбор после ответа.',
                'source_note': 'РИКЗ РТ/ДРТ',
            },
        )
        return topic

    def _import_tasks(self, topic: Topic, bank) -> int:
        created = 0
        for parsed in bank.tasks:
            raw = parsed.correct_answer
            if '|||' in raw:
                answer, explanation = raw.split('|||', 1)
            else:
                answer, explanation = raw, ''
            source = f'{SOURCE_PREFIX} / {bank.filename} / №{parsed.number}'
            if Task.objects.filter(source=source).exists():
                continue
            fmt = (
                Task.AnswerFormat.MULTIPLE_CHOICE
                if parsed.answer_format == 'multiple_choice'
                else Task.AnswerFormat.TEXT
            )
            task = Task.objects.create(
                topic=topic,
                question=parsed.question,
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
            if fmt == Task.AnswerFormat.MULTIPLE_CHOICE and parsed.option_labels:
                correct_nums = {
                    int(x.strip()) for x in answer.split(',') if x.strip().isdigit()
                }
                for idx, label in enumerate(parsed.option_labels, start=1):
                    TaskOption.objects.create(
                        task=task,
                        text=f'{idx}) {label}',
                        is_correct=idx in correct_nums,
                        order=idx,
                    )
            elif fmt == Task.AnswerFormat.MULTIPLE_CHOICE:
                task.answer_format = Task.AnswerFormat.TEXT
                task.scoring_scheme = Task.ScoringScheme.BINARY_2
                task.save(update_fields=['answer_format', 'scoring_scheme'])

            TaskSolution.objects.create(
                task=task,
                correct_answer=answer.strip(),
                explanation=explanation or f'Ключ: {answer}',
                common_mistakes='',
            )
            created += 1
        return created
