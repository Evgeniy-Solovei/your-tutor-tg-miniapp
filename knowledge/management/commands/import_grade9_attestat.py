"""Импорт структуры 9 класса (аттестат): разделы и темы из учебника/программы.

Не создаёт тестовые задания ЦТ — у 9 класса экзамен = изложение.
Задания появятся после сборника текстов изложений в exam_texts/.

  python manage.py import_grade9_attestat
  python manage.py import_grade9_attestat --clear-topics
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import ContentVersion, ExamTrack, Section, Subject, Topic, TopicSummary

# Структура по оглавлению учебника Мурина и др. 2025 (9 класс)
GRADE9_SECTIONS = [
    {
        'name': 'Повторение (8 класс)',
        'order': 1,
        'topics': [
            'Словосочетание. Простое предложение',
            'Простое осложнённое предложение',
        ],
    },
    {
        'name': 'Текст. Стили речи',
        'order': 2,
        'topics': [
            'Основные признаки текста',
            'Синтаксическая синонимия',
            'Языковые средства стилей',
            'Обучающее изложение (повествование)',
        ],
    },
    {
        'name': 'Жанры речи',
        'order': 3,
        'topics': [
            'Отзыв',
            'Реферат',
        ],
    },
    {
        'name': 'Сложное предложение',
        'order': 4,
        'topics': [
            'Строение сложного предложения',
        ],
    },
    {
        'name': 'Сложносочинённое предложение',
        'order': 5,
        'topics': [
            'Основные группы ССП',
            'Знаки препинания в ССП',
            'ССП с соединительными союзами',
            'ССП с разделительными союзами',
            'ССП с противительными союзами',
        ],
    },
    {
        'name': 'Сложноподчинённое предложение',
        'order': 6,
        'topics': [
            'Строение СПП. Знаки препинания',
            'Средства связи в СПП',
            'Виды придаточных',
            'Придаточные определительные',
            'Придаточные изъяснительные',
            'Придаточные места',
            'Придаточные времени',
            'Придаточные причины, следствия, цели',
            'Придаточные условия, уступки',
            'Придаточные образа действия и степени',
            'Придаточные сравнительные',
            'СПП с несколькими придаточными',
        ],
    },
    {
        'name': 'Бессоюзное сложное предложение',
        'order': 7,
        'topics': [
            'Строение и значение БСП',
            'Запятая и точка с запятой в БСП',
            'Двоеточие в БСП',
            'Тире в БСП',
        ],
    },
    {
        'name': 'Сложное предложение с разными видами связи',
        'order': 8,
        'topics': [
            'Разные виды союзной и бессоюзной связи',
            'Знаки препинания при разных видах связи',
        ],
    },
    {
        'name': 'Чужая речь',
        'order': 9,
        'topics': [
            'Способы передачи чужой речи',
            'Прямая речь',
            'Диалог',
            'Косвенная речь',
            'Цитация и эпиграф',
        ],
    },
    {
        'name': 'Пунктуация (повторение)',
        'order': 10,
        'topics': [
            'Знаки препинания и их роль',
            'Знаки конца предложения',
            'Употребление запятой',
            'Двоеточие, тире, кавычки',
        ],
    },
]


class Command(BaseCommand):
    help = 'Структура тем 9 класса (аттестат) из учебника Мурина 2025'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-topics',
            action='store_true',
            help='Удалить темы/разделы трека attestat_9 перед импортом',
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            subject, _ = Subject.objects.get_or_create(
                slug='russian',
                defaults={'name': 'Русский язык', 'order': 1, 'is_active': True},
            )
            track, _ = ExamTrack.objects.update_or_create(
                subject=subject,
                track_type=ExamTrack.TrackType.ATTESTAT_9,
                defaults={
                    'name': 'Аттестат / базовое образование (после 9 класса)',
                    'grade_from': 8,
                    'grade_to': 9,
                    'is_active': True,
                },
            )
            version, _ = ContentVersion.objects.update_or_create(
                subject=subject,
                year=2025,
                title='9 класс: программа V–IX + учебник Мурина 2025',
                defaults={
                    'source_url': 'https://adu.by/',
                    'is_current': False,
                    'notes': (
                        'Материалы: materials/russian/09_klass/. '
                        'Экзамен = изложение. Тестовый банк ЦТ сюда не копируем. '
                        'Тексты изложений — в exam_texts/ (покупается отдельно).'
                    ),
                },
            )

            if options['clear_topics']:
                deleted, _ = Section.objects.filter(exam_track=track).delete()
                self.stdout.write(f'Удалено разделов (и каскад тем): {deleted}')

            topics_n = 0
            for sec_spec in GRADE9_SECTIONS:
                section, _ = Section.objects.get_or_create(
                    exam_track=track,
                    content_version=version,
                    name=sec_spec['name'],
                    defaults={'order': sec_spec['order']},
                )
                for i, topic_name in enumerate(sec_spec['topics'], start=1):
                    topic, created = Topic.objects.get_or_create(
                        section=section,
                        name=topic_name,
                        defaults={
                            'grade_level': 9,
                            'exam_weight': 1.0,
                            'order': i,
                            'is_active': True,
                        },
                    )
                    if created:
                        topics_n += 1
                    TopicSummary.objects.update_or_create(
                        topic=topic,
                        defaults={
                            'title': f'9 класс: {topic_name}',
                            'content': (
                                f'Тема по программе и учебнику русского языка 9 класса (РБ). '
                                f'Выпускной экзамен II ступени — изложение, не тест ЦТ/ЦЭ. '
                                f'Отрабатывай синтаксис, пунктуацию и связную письменную речь.'
                            ),
                            'key_points': 'См. учебник Мурина и др. 2025; программа V–IX 2025.',
                            'source_note': 'materials/russian/09_klass/ (учебник + программа)',
                        },
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: трек attestat_9, версия контента id={version.id}, '
                f'новых тем: {topics_n}. Заданий пока 0 — нужен сборник изложений.'
            )
        )
