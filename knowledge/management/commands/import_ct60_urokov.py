"""
Импорт пособия «Русский язык. ЦТ за 60 уроков» (Бычковская, Долбик, Леонович, Облова, 5 изд., 2019).

  python manage.py import_ct60_urokov
  python manage.py import_ct60_urokov --clear
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.ct60_parser import parse_ct60_pdf
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

DEFAULT_PDF = (
    'materials/russian/11_klass/practice/trenazher/'
    'CT_za_60_urokov_Bychkovskaya_Dolbik_Leonovich_Oblova_5ed_2019.pdf'
)
SOURCE_PREFIX = 'ЦТ за 60 уроков'


class Command(BaseCommand):
    help = 'Импорт заданий из «ЦТ за 60 уроков» (с ключами и комментариями)'

    def add_arguments(self, parser):
        parser.add_argument('--pdf', default=DEFAULT_PDF, help='Путь к PDF')
        parser.add_argument(
            '--clear',
            action='store_true',
            help=f'Удалить задания с source начиная с «{SOURCE_PREFIX}»',
        )

    def handle(self, *args, **options):
        pdf = Path(options['pdf'])
        if not pdf.is_absolute():
            pdf = Path(settings.BASE_DIR) / pdf
        if not pdf.exists():
            self.stderr.write(self.style.ERROR(f'PDF не найден: {pdf}'))
            return

        with transaction.atomic():
            subject, track, version = self._ensure_structure()
            if options['clear']:
                deleted, _ = Task.objects.filter(source__startswith=SOURCE_PREFIX).delete()
                self.stdout.write(f'Удалено заданий: {deleted}')

            sections = parse_ct60_pdf(pdf)
            total = 0
            for block in sections:
                section = self._ensure_section(track, version, block.section_title)
                topic = self._ensure_topic(section, block.section_title, block.test_number)
                created = self._import_tasks(topic, block.tasks, block)
                total += created
                self.stdout.write(
                    f'{block.section_title} / тест {block.test_number}: +{created}'
                )

            ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=str(pdf.relative_to(settings.BASE_DIR)),
                defaults={
                    'title': 'Русский язык. ЦТ за 60 уроков (5-е изд.)',
                    'publisher': 'Аверсэв / Бычковская и др.',
                    'year': 2019,
                    'is_active': True,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'Готово. Импортировано заданий: {total}'))

    def _ensure_structure(self):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={
                'name': 'Русский язык',
                'description': 'Подготовка к ЦТ/ЦЭ по русскому языку (Беларусь)',
                'order': 1,
                'is_active': True,
            },
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
            year=2019,
            defaults={
                'title': 'ЦТ за 60 уроков (Бычковская и др., 5 изд.)',
                'source_url': '',
                'is_current': False,
                'notes': 'Практика + ключи. PDF в practice/trenazher/.',
            },
        )
        return subject, track, version

    def _ensure_section(self, track, version, name: str) -> Section:
        order_map = {
            'Диагностические тесты': 0,
            'Орфография': 1,
            'Пунктуация': 2,
            'Лексика': 3,
            'Лексика. Фразеология': 3,
            'Культура речи': 4,
            'Фонетика': 5,
            'Словообразование': 6,
            'Морфология': 7,
            'Синтаксис': 8,
            'Итоговые тесты': 9,
        }
        section, _ = Section.objects.get_or_create(
            exam_track=track,
            content_version=version,
            name=f'60 уроков · {name}',
            defaults={'order': order_map.get(name, 50)},
        )
        return section

    def _ensure_topic(self, section: Section, section_name: str, test_number: int) -> Topic:
        topic, _ = Topic.objects.get_or_create(
            section=section,
            name=f'Тест {test_number}',
            defaults={
                'grade_level': 11,
                'exam_weight': 1.0,
                'order': test_number,
                'is_active': True,
            },
        )
        TopicSummary.objects.update_or_create(
            topic=topic,
            defaults={
                'title': f'ЦТ за 60 уроков — {section_name}, тест {test_number}',
                'content': (
                    f'Задания из пособия «ЦТ за 60 уроков» ({section_name}), тест {test_number}.'
                ),
                'key_points': 'Сверяй ответ с ключом; читай комментарий к ошибкам.',
                'source_note': 'Бычковская Ж.Э. и др. Русский язык. ЦТ за 60 уроков. 5-е изд., 2019',
            },
        )
        return topic

    def _import_tasks(self, topic: Topic, tasks, block) -> int:
        created = 0
        for parsed in tasks:
            raw = parsed.correct_answer
            if '|||' in raw:
                answer, explanation = raw.split('|||', 1)
            else:
                answer, explanation = raw, ''
            answer = answer.strip()
            source = (
                f'{SOURCE_PREFIX} / {block.section_title} / '
                f'тест {block.test_number} / №{parsed.number}'
            )
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
                scoring_scheme=Task.ScoringScheme.PARTIAL_2
                if fmt == Task.AnswerFormat.MULTIPLE_CHOICE
                else Task.ScoringScheme.BINARY_2,
            )

            if fmt == Task.AnswerFormat.MULTIPLE_CHOICE and parsed.option_labels:
                correct_nums = {
                    int(x.strip())
                    for x in answer.split(',')
                    if x.strip().isdigit()
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
                correct_answer=answer,
                explanation=explanation
                or f'Ключ пособия «ЦТ за 60 уроков»: {answer}',
                common_mistakes='',
            )
            created += 1
        return created
