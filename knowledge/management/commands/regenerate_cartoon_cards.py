"""
Команда массовой перегенерации иллюстраций к доп. заданиям (1–5 классы)
в мультяшных стилях (Roblox, Toca Boca, Маша и Медведь, Minecraft, Brawl Stars).

НИКАКИХ СПОЙЛЕРОВ: карточка никогда не показывает правильный ответ.
"""
from __future__ import annotations

import os
from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge.models import TopicExtraTask, Topic
from knowledge.management.commands.cartoon_card_art import render_kid_cartoon_card


class Command(BaseCommand):
    help = 'Перерисовать карточки заданий 1–5 классов в детских мульт-стилях без спойлеров'

    def add_arguments(self, parser):
        parser.add_argument('--grade', type=int, default=0, help='Класс (1-5, 0 = все 1-5)')
        parser.add_argument('--topic-id', type=int, default=0, help='ID конкретной темы')
        parser.add_argument('--limit', type=int, default=0, help='Ограничить количество (для теста)')
        parser.add_argument('--per-topic', type=int, default=0, help='Ограничить N первыми заданиями темы')

    def handle(self, *args, **options):
        grade_opt = options['grade']
        grades = [grade_opt] if grade_opt in (1, 2, 3, 4, 5) else [1, 2, 3, 4, 5]
        media_root = settings.MEDIA_ROOT

        qs = TopicExtraTask.objects.filter(
            topic__grade_level__in=grades,
            is_active=True,
        ).select_related('topic').order_by('topic__grade_level', 'topic_id', 'order', 'id')

        if options['topic_id']:
            qs = qs.filter(topic_id=options['topic_id'])

        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f'=== Перегенерация карточек в стиле мультиков (Roblox, Toca Boca, Маша, Minecraft, Brawl Stars) ==='
        ))
        self.stdout.write(f'Всего заданий в пуле: {total}')

        limit = options['limit']
        per_topic = options['per_topic']
        processed = 0
        current_topic_id = None
        topic_count = 0

        for task in qs.iterator(chunk_size=500):
            if limit and processed >= limit:
                break

            if task.topic_id != current_topic_id:
                current_topic_id = task.topic_id
                topic_count = 0
                self.stdout.write(f'Класс {task.topic.grade_level} · Тема {task.topic.id} «{task.topic.name}»…')

            if per_topic and topic_count >= per_topic:
                continue

            # Определяем путь к картинке
            if task.image and task.image.name:
                img_rel = task.image.name
            else:
                img_rel = f'extra_tasks/grade{task.topic.grade_level}/topic_{task.topic_id}/task_{task.order or task.id}.png'

            img_full = os.path.join(media_root, img_rel)

            # Рендерим мультяшную карточку без спойлера
            render_kid_cartoon_card(
                file_path=img_full,
                topic_name=task.topic.name,
                question_text=task.question,
                correct_answer=task.correct_answer,
                style_idx=task.topic_id + (task.order or task.id),
                grade=task.topic.grade_level,
            )

            # Если поле image в БД было пустым — прописываем
            if not task.image:
                task.image = img_rel
                task.image_url = f'/media/{img_rel}'
                task.save(update_fields=['image', 'image_url'])

            processed += 1
            topic_count += 1

            if processed % 100 == 0:
                self.stdout.write(f'  ✓ Обработано {processed} карточек…')

        self.stdout.write(self.style.SUCCESS(
            f'✓ Готово! Успешно перерисовано {processed} карточек в мультяшных стилях без спойлеров!'
        ))
