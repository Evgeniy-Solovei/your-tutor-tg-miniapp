"""
Загружает программы и задания открытого банка РИКЗ.

По умолчанию:
  materials/russian/11_klass/  (PDF в open_bank/)

Использование:
  python manage.py import_rikz_bank
  python manage.py import_rikz_bank --clear
  python manage.py import_rikz_bank --dir materials/russian/11_klass
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import (
    ContentVersion,
    ExamTrack,
    Section,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    Topic,
    TopicSummary,
)
from knowledge.pdf_parser import parse_all_bank_pdfs
from knowledge.topic_content import TOPIC_SUMMARIES

DEFAULT_MATERIALS_DIR = 'materials/russian/11_klass'


class Command(BaseCommand):
    help = 'Импорт открытого банка РИКЗ (ЦТ/ЦЭ, 11 класс) из materials/russian/11_klass/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            default=DEFAULT_MATERIALS_DIR,
            help=f'Папка с материалами (по умолчанию {DEFAULT_MATERIALS_DIR})',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Удалить ранее импортированные задания из открытого банка',
        )

    def handle(self, *args, **options):
        info_dir = Path(options['dir'])
        if not info_dir.is_absolute():
            info_dir = Path(settings.BASE_DIR) / info_dir
        if not info_dir.exists():
            self.stdout.write(self.style.WARNING(f'Папка с PDF не найдена: {info_dir} (пропускаем импорт файлов)'))
            return

        with transaction.atomic():
            subject, track, version = self._ensure_structure()
            if options['clear']:
                deleted, _ = Task.objects.filter(source__startswith='РИКЗ открытый банк').delete()
                self.stdout.write(f'Удалено заданий: {deleted}')

            bank_files = parse_all_bank_pdfs(info_dir)
            total_tasks = 0
            for bank in bank_files:
                section = self._ensure_section(track, version, bank.section_name)
                topic = self._ensure_topic(section, bank.section_name, bank.part_name)
                created = self._import_tasks(topic, bank)
                total_tasks += created
                self.stdout.write(
                    f'{bank.filename}: {bank.section_name} / {bank.part_name} → {created} заданий'
                )

        self.stdout.write(self.style.SUCCESS(
            f'Готово. Импортировано заданий: {total_tasks}. Предмет: {subject.name}, трек: {track.name}'
        ))

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
            year=2026,
            defaults={
                'title': 'Открытый банк РИКЗ ЦТ/ЦЭ (10–11) + программы 2025/2026',
                'source_url': 'https://rikc.by/otkrytyj-bank-testovyh-materialov/',
                'is_current': True,
                'notes': 'Материалы в materials/russian/11_klass/. Полные сборники — в variants/.',
            },
        )
        return subject, track, version

    def _ensure_section(self, track, version, section_name: str) -> Section:
        order_map = {
            'Орфография': 1,
            'Пунктуация': 2,
            'Лексика': 3,
            'Культура речи': 4,
            'Фонетика': 5,
            'Состав слова. Образование слов': 6,
            'Морфология': 7,
            'Синтаксис': 8,
            'Текст': 9,
        }
        section, _ = Section.objects.get_or_create(
            exam_track=track,
            content_version=version,
            name=section_name,
            defaults={'order': order_map.get(section_name, 99)},
        )
        return section

    def _ensure_topic(self, section: Section, section_name: str, part_name: str) -> Topic:
        topic_name = f'{section_name} — {part_name}'
        topic, created = Topic.objects.get_or_create(
            section=section,
            name=topic_name,
            defaults={
                'grade_level': 11,
                'exam_weight': 1.0,
                'order': int(part_name.split()[-1]) if part_name.split()[-1].isdigit() else 1,
                'is_active': True,
            },
        )
        data = TOPIC_SUMMARIES.get(section_name, {})
        TopicSummary.objects.update_or_create(
            topic=topic,
            defaults={
                'title': data.get('title', f'Конспект: {section_name}'),
                'content': data.get(
                    'content',
                    f'Основные правила раздела «{section_name}» по программе РБ.',
                ),
                'key_points': data.get('key_points', 'Используй примеры из заданий открытого банка РИКЗ.'),
                'source_note': 'РИКЗ открытый банк / учебная программа Минобразования РБ',
            },
        )
        return topic

    def _import_tasks(self, topic: Topic, bank) -> int:
        created_count = 0
        for parsed in bank.tasks:
            source = f'РИКЗ открытый банк / {bank.filename} / №{parsed.number}'
            if Task.objects.filter(topic=topic, source=source).exists():
                continue

            answer_format = (
                Task.AnswerFormat.MULTIPLE_CHOICE
                if parsed.answer_format == 'multiple_choice'
                else Task.AnswerFormat.TEXT
            )

            task = Task.objects.create(
                topic=topic,
                question=parsed.question,
                answer_format=answer_format,
                difficulty=Task.Difficulty.MEDIUM,
                source=source,
                is_active=True,
            )

            if answer_format == Task.AnswerFormat.MULTIPLE_CHOICE and parsed.option_labels:
                correct_nums = {
                    int(x.strip())
                    for x in parsed.correct_answer.split(',')
                    if x.strip().isdigit()
                }
                for idx, label in enumerate(parsed.option_labels, start=1):
                    TaskOption.objects.create(
                        task=task,
                        text=f'{idx}) {label}',
                        is_correct=idx in correct_nums,
                        order=idx,
                    )
            elif answer_format == Task.AnswerFormat.MULTIPLE_CHOICE:
                # Варианты не распознаны — сохраняем как текст
                task.answer_format = Task.AnswerFormat.TEXT
                task.save(update_fields=['answer_format'])

            TaskSolution.objects.create(
                task=task,
                correct_answer=parsed.correct_answer,
                explanation=(
                    f'Правильный ответ по ключу РИКЗ: {parsed.correct_answer}. '
                    f'Раздел: {bank.section_name} ({bank.part_name}).'
                ),
                common_mistakes='',
            )
            created_count += 1
        return created_count
