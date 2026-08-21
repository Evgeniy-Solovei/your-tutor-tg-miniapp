"""
Импорт «Русский язык. ЦТ. Тренажёр» (Долбик и др., Аверсэв).

  python manage.py import_aversev_trenazher
  python manage.py import_aversev_trenazher --clear
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.aversev_trenazher_parser import parse_aversev_trenazher
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

SOURCE_PREFIX = 'ЦТ тренажёр Аверсэв'
DEFAULT_PDF = (
    'materials/russian/11_klass/practice/trenazher/'
    'CT_trenazher_Dolbik_Aversev_2ed_2019_PARTIAL_KEYS.pdf'
)


class Command(BaseCommand):
    help = 'Импорт тренажёра ЦТ Аверсэв (Долбик и др.) с ключами'

    def add_arguments(self, parser):
        parser.add_argument('--pdf', default=DEFAULT_PDF)
        parser.add_argument('--clear', action='store_true')
        parser.add_argument(
            '--answer-block',
            type=int,
            default=0,
            help='только N-й блок «Ответы» в PDF (1=орфография, 0=все)',
        )
        parser.add_argument('--roman-from', default='')
        parser.add_argument('--roman-to', default='')
        parser.add_argument(
            '--clear-block',
            action='store_true',
            help='удалить задания только текущего --answer-block перед импортом',
        )

    def handle(self, *args, **options):
        pdf = Path(options['pdf'])
        if not pdf.is_absolute():
            pdf = Path(settings.BASE_DIR) / pdf
        if not pdf.exists():
            self.stderr.write(self.style.ERROR(f'Нет файла: {pdf}'))
            return

        block = options['answer_block'] or None
        roman_from = options['roman_from'] or None
        roman_to = options['roman_to'] or None
        bank = parse_aversev_trenazher(
            pdf,
            answer_block=block,
            roman_from=roman_from,
            roman_to=roman_to,
        )
        self.stdout.write(f'Разобрано заданий: {len(bank.tasks)}')

        with transaction.atomic():
            subject, track, version = self._ensure_structure()
            if options['clear']:
                deleted, _ = Task.objects.filter(source__startswith=SOURCE_PREFIX).delete()
                self.stdout.write(f'Удалено: {deleted}')
            elif options['clear_block'] and block:
                deleted, _ = Task.objects.filter(
                    source__startswith=f'{SOURCE_PREFIX} / b{block} /'
                ).delete()
                self.stdout.write(f'Удалено блок {block}: {deleted}')

            section, _ = Section.objects.get_or_create(
                exam_track=track,
                content_version=version,
                name='ЦТ тренажёр Аверсэв (Долбик)',
                defaults={'order': 15},
            )
            # group by section tag in question
            by_sec: dict[str, list] = {}
            for t in bank.tasks:
                m = __import__('re').match(r'\[([^\]]+)', t.question)
                key = (m.group(1).split('·')[0].strip() if m else 'Прочее')
                by_sec.setdefault(key, []).append(t)

            total = 0
            for sec_name, items in by_sec.items():
                topic, _ = Topic.objects.get_or_create(
                    section=section,
                    name=sec_name[:200],
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
                        'title': f'Тренажёр ЦТ — {sec_name}',
                        'content': 'Задания из пособия «Русский язык. ЦТ. Тренажёр» (Аверсэв).',
                        'key_points': 'Сверяй ключ в конце раздела пособия.',
                        'source_note': 'Долбик Е.Е. и др. ЦТ. Тренажёр. 2-е изд., Аверсэв',
                    },
                )
                total += self._import(topic, items, block)

            ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=str(pdf.relative_to(settings.BASE_DIR)),
                defaults={
                    'title': 'Русский язык. ЦТ. Тренажёр (Долбик и др., Аверсэв, 2 изд.)',
                    'publisher': 'Аверсэв',
                    'year': 2019,
                    'is_active': True,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'Импортировано: {total}'))

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
            title='ЦТ тренажёр Аверсэв + ЦТ за 60 уроков',
            defaults={
                'year': 2019,
                'is_current': False,
                'notes': 'practice/trenazher/',
            },
        )
        return subject, track, version

    def _import(self, topic: Topic, items, block: int | None) -> int:
        created = 0
        for parsed in items:
            # стабильный id: блок + метка из вопроса + номер
            m = __import__('re').search(r'\[([^\]]+)\s·\s(?:№)?([АAВB\d]+)\]', parsed.question)
            if m:
                tag = m.group(1).replace(' · ', '/')[:120]
                qn = m.group(2)
                source = f'{SOURCE_PREFIX} / b{block or 0} / {tag} / {qn}'
            else:
                source = f'{SOURCE_PREFIX} / b{block or 0} / {parsed.number}'
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
                correct = {
                    int(x.strip())
                    for x in parsed.correct_answer.split(',')
                    if x.strip().isdigit()
                }
                for idx, label in enumerate(parsed.option_labels, start=1):
                    TaskOption.objects.create(
                        task=task,
                        text=f'{idx}) {label}'[:500],
                        is_correct=idx in correct,
                        order=idx,
                    )
            elif fmt == Task.AnswerFormat.MULTIPLE_CHOICE:
                task.answer_format = Task.AnswerFormat.TEXT
                task.scoring_scheme = Task.ScoringScheme.BINARY_2
                task.save(update_fields=['answer_format', 'scoring_scheme'])

            TaskSolution.objects.create(
                task=task,
                correct_answer=parsed.correct_answer,
                explanation=f'Ключ тренажёра Аверсэв: {parsed.correct_answer}',
                common_mistakes='',
            )
            created += 1
        return created
