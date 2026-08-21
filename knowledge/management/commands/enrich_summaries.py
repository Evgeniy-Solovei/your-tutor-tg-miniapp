from django.core.management.base import BaseCommand

from knowledge.models import Topic, TopicSummary
from knowledge.topic_content import TOPIC_SUMMARIES, section_base_name


class Command(BaseCommand):
    help = 'Обновляет конспекты тем для ИИ-разбора ошибок'

    def handle(self, *args, **options):
        updated = 0
        for topic in Topic.objects.select_related('section').all():
            base = section_base_name(topic.name)
            data = TOPIC_SUMMARIES.get(base) or TOPIC_SUMMARIES.get(topic.section.name)
            if not data:
                continue
            _, created = TopicSummary.objects.update_or_create(
                topic=topic,
                defaults={
                    'title': data['title'],
                    'content': data['content'],
                    'key_points': data['key_points'],
                    'source_note': 'Методическая выжимка по программе РБ / открытый банк РИКЗ',
                },
            )
            updated += 1
            self.stdout.write(f'{"+" if created else "~"} {topic.name}')
        self.stdout.write(self.style.SUCCESS(f'Обновлено конспектов: {updated}'))
