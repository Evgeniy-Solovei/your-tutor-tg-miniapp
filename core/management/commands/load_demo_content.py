from django.core.management.base import BaseCommand

from core.models import AppSettings, City, School
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


class Command(BaseCommand):
    help = 'Загружает демо-контент: предмет, трек, темы и задания для тестирования бота'

    def handle(self, *args, **options):
        AppSettings.objects.get_or_create(pk=1)

        city, _ = City.objects.get_or_create(name='Минск', defaults={'region': 'Минская'})
        School.objects.get_or_create(city=city, name='Гимназия №1')

        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'order': 1},
        )

        track, _ = ExamTrack.objects.get_or_create(
            subject=subject,
            track_type=ExamTrack.TrackType.CT_11,
            defaults={
                'name': 'ЦТ по русскому языку (11 класс)',
                'grade_from': 5,
                'grade_to': 11,
            },
        )

        version, _ = ContentVersion.objects.get_or_create(
            subject=subject,
            year=2026,
            defaults={
                'title': 'Программа и спецификация РИКЗ 2026',
                'is_current': True,
            },
        )

        section, _ = Section.objects.get_or_create(
            exam_track=track,
            content_version=version,
            name='Синтаксис',
            defaults={'order': 1},
        )

        topics_data = [
            ('Причастный оборот', 8),
            ('Обособленные определения', 9),
            ('Сложное предложение', 10),
        ]

        for order, (name, grade) in enumerate(topics_data):
            topic, created = Topic.objects.get_or_create(
                section=section,
                name=name,
                defaults={'grade_level': grade, 'order': order, 'exam_weight': 1.0},
            )
            if created:
                TopicSummary.objects.create(
                    topic=topic,
                    title=f'Конспект: {name}',
                    content=(
                        f'Краткий конспект по теме «{name}». '
                        'Заполните в админке текст из учебника или методички РИКЗ.'
                    ),
                    key_points='Добавьте ключевые правила в админке.',
                    source_note='Демо-данные',
                )

        topic = Topic.objects.filter(section=section).first()
        if topic and not Task.objects.filter(topic=topic).exists():
            task = Task.objects.create(
                topic=topic,
                question='Укажите предложение с причастным оборотом:',
                answer_format=Task.AnswerFormat.SINGLE_CHOICE,
                difficulty=Task.Difficulty.MEDIUM,
                source='Демо / сборник РИКЗ',
            )
            TaskOption.objects.bulk_create(
                [
                    TaskOption(task=task, text='Бегущий по полю мальчик остановился.', is_correct=True, order=1),
                    TaskOption(task=task, text='Мальчик бежал по полю быстро.', is_correct=False, order=2),
                    TaskOption(task=task, text='На поле росла трава.', is_correct=False, order=3),
                    TaskOption(task=task, text='Вчера мы гуляли в парке.', is_correct=False, order=4),
                ]
            )
            TaskSolution.objects.create(
                task=task,
                correct_answer='Бегущий по полю мальчик остановился.',
                explanation=(
                    'Причастный оборот «Бегущий по полю» стоит перед определяемым словом «мальчик» '
                    'и отделяется от него по смыслу.'
                ),
                common_mistakes='Путают с деепричастным оборотом.',
            )

        self.stdout.write(self.style.SUCCESS('Демо-контент загружен. Создай суперпользователя и запусти бота.'))
