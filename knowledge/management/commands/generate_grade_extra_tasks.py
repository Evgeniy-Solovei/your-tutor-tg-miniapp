"""
Генерация дополнительных заданий по темам класса (с картинками для 1–4).

Цель: 100 заданий на тему (позже расширяем до 1000).

  ./venv/bin/python manage.py generate_grade_extra_tasks --grade 1 --per-topic 100
  ./venv/bin/python manage.py generate_grade_extra_tasks --grade 2 --per-topic 100
  ./venv/bin/python manage.py generate_grade_extra_tasks --grade 1 --per-topic 100 --topic-id 42
"""
from __future__ import annotations

import os
import random

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from knowledge.models import Task, Topic, TopicExtraTask


SOURCE_TAG = 'illustrated_extra_v100'


class Command(BaseCommand):
    help = 'Доп. задания: N штук на каждую тему выбранного класса'

    def add_arguments(self, parser):
        parser.add_argument('--grade', type=int, required=True)
        parser.add_argument('--per-topic', type=int, default=100)
        parser.add_argument('--topic-id', type=int, default=0)
        parser.add_argument(
            '--only-below',
            type=int,
            default=0,
            help='Только темы, где активных доп. меньше этого числа (например 100)',
        )
        parser.add_argument('--no-images', action='store_true')
        parser.add_argument('--replace', action='store_true', help='Удалить старые доп. по теме перед генерацией')

    def handle(self, *args, **options):
        grade = options['grade']
        per = options['per_topic']
        self.stdout.write(self.style.NOTICE(
            f'=== Доп. задания: {grade} класс × {per} на тему ==='
        ))

        textbook_qs = set(
            Task.objects.filter(topic__grade_level=grade).values_list('question', flat=True)[:5000]
        )

        topics = Topic.objects.filter(grade_level=grade, is_active=True).order_by('id')
        if options['topic_id']:
            topics = topics.filter(id=options['topic_id'])
        if options['only_below']:
            topics = topics.annotate(
                extra_n=Count('extra_tasks', filter=Q(extra_tasks__is_active=True))
            ).filter(extra_n__lt=options['only_below'])

        topics = list(topics)
        self.stdout.write(f'Тем к обработке: {len(topics)}')

        if grade == 1:
            from knowledge.management.commands.generators_grade1 import generate_tasks_for_topic
            from knowledge.management.commands.generate_grade1_extra_tasks import (
                PALETTES,
                render_card_image,
            )
            gen_fn = generate_tasks_for_topic
            use_images = not options['no_images']
        elif grade == 2:
            from knowledge.management.commands.generators_grade2 import generate_tasks_for_topic
            from knowledge.management.commands.generate_grade1_extra_tasks import (
                PALETTES,
                render_card_image,
            )
            gen_fn = generate_tasks_for_topic
            use_images = not options['no_images']
        elif grade == 3:
            from knowledge.management.commands.generators_grade3 import generate_tasks_for_topic
            from knowledge.management.commands.generate_grade1_extra_tasks import (
                PALETTES,
                render_card_image,
            )
            gen_fn = generate_tasks_for_topic
            use_images = not options['no_images']
        elif grade == 4:
            from knowledge.management.commands.generators_grade4 import generate_tasks_for_topic
            from knowledge.management.commands.generate_grade1_extra_tasks import (
                PALETTES,
                render_card_image,
            )
            gen_fn = generate_tasks_for_topic
            use_images = not options['no_images']
        else:
            from knowledge.management.commands.generators_grade2 import generate_tasks_for_topic
            try:
                from knowledge.management.commands.generate_grade1_extra_tasks import (
                    PALETTES,
                    render_card_image,
                )
                use_images = not options['no_images'] and grade <= 4
            except Exception:
                PALETTES = []
                render_card_image = None
                use_images = False
            gen_fn = generate_tasks_for_topic

        total_created = 0
        media_root = settings.MEDIA_ROOT
        mascots = ['bear', 'fox', 'bunny', 'cat', 'frog']

        for topic_idx, topic in enumerate(topics, 1):
            existing = TopicExtraTask.objects.filter(topic=topic, is_active=True).count()
            if existing >= per and not options['replace']:
                self.stdout.write(
                    f'[{topic_idx}/{len(topics)}] «{topic.name}»: уже {existing} (≥{per}), пропуск'
                )
                continue

            tasks_data = gen_fn(topic.id, topic.name, textbook_qs, count=per)
            if options['replace']:
                TopicExtraTask.objects.filter(topic=topic).delete()
                start_order = 1
                need = per
            else:
                start_order = existing + 1
                need = max(0, per - existing)
                tasks_data = tasks_data[:need]

            created_for_topic = 0
            for i, item in enumerate(tasks_data, start=start_order):
                opts = list(item.get('options') or [])
                random.shuffle(opts)
                # correct must stay in options
                correct = item['correct_answer']
                if correct not in opts:
                    opts = [correct] + [o for o in opts if o != correct][:3]
                    random.shuffle(opts)

                img_rel = ''
                img_url = ''
                if use_images and render_card_image:
                    img_rel_dir = f'extra_tasks/grade{grade}/topic_{topic.id}'
                    img_filename = f'task_{i}.png'
                    img_full = os.path.join(media_root, img_rel_dir, img_filename)
                    render_card_image(
                        file_path=img_full,
                        topic_name=topic.name,
                        focus_word=item.get('card_word', topic.name)[:40],
                        rule_text=item.get('card_rule', f'Правило {grade} класса')[:60],
                        mascot_name=mascots[(topic.id + i) % len(mascots)],
                        palette_idx=(topic.id + i) % max(1, len(PALETTES)),
                    )
                    img_rel = f'{img_rel_dir}/{img_filename}'
                    img_url = f'/media/{img_rel}'

                TopicExtraTask.objects.create(
                    topic=topic,
                    question=item['question'],
                    reading_text=item.get('reading_text', ''),
                    image=img_rel,
                    image_url=img_url,
                    options=opts,
                    correct_answer=correct,
                    explanation=item.get('explanation', ''),
                    difficulty=item.get('difficulty', 'medium'),
                    order=i,
                    source=SOURCE_TAG,
                    is_active=True,
                )
                created_for_topic += 1
                total_created += 1

            self.stdout.write(
                f'[{topic_idx}/{len(topics)}] «{topic.name}»: +{created_for_topic} '
                f'(цель {per})'
            )

        self.stdout.write(self.style.SUCCESS(f'✓ Создано {total_created} доп. заданий'))
