"""
Структура программы 10 класса по учебнику Леонович и др. (2020).

Создаёт разделы/темы на треке GENERAL с grade_level=10.
Задания из учебника пока не извлекаются автоматически.

  python manage.py import_grade10_structure
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import ContentVersion, ExamTrack, Section, Subject, Topic, TopicSummary


GRADE10_SECTIONS: list[dict] = [
    {
        'name': 'Повторение изученного в 8–9 классах',
        'order': 1,
        'topics': [
            'Предложение как единица синтаксиса',
            'Пунктуация в конструкциях с «как»',
        ],
    },
    {
        'name': 'Общие сведения о языке',
        'order': 2,
        'topics': [
            'Русский язык как развивающееся явление',
            'Русский язык как государственный язык Республики Беларусь',
            'Русский язык в международном общении',
        ],
    },
    {
        'name': 'Текст и его признаки',
        'order': 3,
        'topics': [
            'Единицы текста и его признаки',
            'Тематическое единство и развёрнутость',
            'Последовательность и смысловая цельность текста',
            'Структурная связность текста',
        ],
    },
    {
        'name': 'Культура речи',
        'order': 4,
        'topics': ['Коммуникативные качества речи'],
    },
    {
        'name': 'Функциональные стили речи',
        'order': 5,
        'topics': ['Функциональные стили и их признаки'],
    },
    {
        'name': 'Жанры речи: дискуссия',
        'order': 6,
        'topics': ['Диалогические жанры речи'],
    },
    {
        'name': 'Слово: звуковая сторона',
        'order': 7,
        'topics': [
            'Гласные и согласные звуки',
            'Ударение',
            'Произносительные нормы',
        ],
    },
    {
        'name': 'Слово: смысловая сторона',
        'order': 8,
        'topics': [
            'Лексическое и грамматическое значение слова',
            'Однозначные и многозначные слова',
            'Омонимы',
            'Синонимы',
            'Антонимы',
            'Фразеологические обороты',
        ],
    },
    {
        'name': 'Состав слова. Образование слов',
        'order': 9,
        'topics': [
            'Состав слова',
            'Образование слов',
            'Словообразовательная норма',
        ],
    },
    {
        'name': 'Морфология',
        'order': 10,
        'topics': [
            'Части речи',
            'Имя существительное',
            'Имя прилагательное',
            'Имя числительное',
            'Местоимение',
            'Глагол и его формы',
            'Наречие',
            'Служебные части речи',
            'Междометие',
        ],
    },
    {
        'name': 'Жанры речи: доклад',
        'order': 11,
        'topics': [
            'Содержание и композиция доклада',
            'Язык доклада',
            'Подготовка к произнесению доклада',
        ],
    },
    {
        'name': 'Орфография',
        'order': 12,
        'topics': [
            'Проверяемые написания',
            'Фонетические написания',
            'Непроверяемые написания',
            'Правописание ъ и ь',
            'Приставки пре- и при-',
            'Правописание имён существительных',
            'Правописание имён прилагательных',
            'Правописание глаголов',
            'Правописание причастий',
            'Н и НН в словах разных частей речи',
            'Суффиксы наречий',
            'Слитные, раздельные и дефисные написания',
            'Правописание НЕ со словами разных частей речи',
            'Правописание НЕ и НИ',
        ],
    },
]


class Command(BaseCommand):
    help = 'Импорт структуры тем 10 класса (учебник Леонович 2020) на трек GENERAL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Удалить разделы трека GENERAL перед импортом',
        )

    def handle(self, *args, **options):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'is_active': True},
        )
        track, created = ExamTrack.objects.update_or_create(
            subject=subject,
            track_type=ExamTrack.TrackType.GENERAL,
            defaults={
                'name': 'Школьная программа (1–11 классы)',
                'grade_from': 1,
                'grade_to': 11,
                'is_active': True,
            },
        )
        self.stdout.write(('✓ создан' if created else '↻ обновлён') + f' трек: {track.name}')

        version, _ = ContentVersion.objects.update_or_create(
            subject=subject,
            year=2020,
            title='Русский язык 10 класс — Леонович и др.',
            defaults={
                'is_current': False,
                'notes': 'Структура по учебнику materials/russian/10_klass/textbooks/',
            },
        )

        with transaction.atomic():
            if options['clear']:
                deleted, _ = Section.objects.filter(exam_track=track).delete()
                self.stdout.write(f'Удалено разделов: {deleted}')

            topic_count = 0
            for sec_spec in GRADE10_SECTIONS:
                section, _ = Section.objects.get_or_create(
                    exam_track=track,
                    content_version=version,
                    name=sec_spec['name'],
                    defaults={'order': sec_spec['order']},
                )
                for t_order, topic_name in enumerate(sec_spec['topics'], start=1):
                    topic, was_created = Topic.objects.get_or_create(
                        section=section,
                        name=topic_name,
                        defaults={
                            'order': t_order,
                            'grade_level': 10,
                            'exam_weight': 1.0,
                            'is_active': True,
                        },
                    )
                    if was_created:
                        topic_count += 1
                    TopicSummary.objects.update_or_create(
                        topic=topic,
                        defaults={
                            'title': f'10 класс: {topic_name}',
                            'content': (
                                f'Тема по учебнику «Русский язык» 10 класс '
                                f'(Леонович и др., 2020). Отрабатывай правило и '
                                f'типовые упражнения; банк ЦТ 11 класса сюда не подмешивается.'
                            ),
                            'key_points': 'См. учебник Леонович 2020; программы 10–11 (базовый/повышенный).',
                            'source_note': 'materials/russian/10_klass/',
                        },
                    )

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {len(GRADE10_SECTIONS)} разделов, новых тем: {topic_count} (grade_level=10).'
        ))
