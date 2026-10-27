"""Пересчитать Topic.extra_task_count по фактическим доп. заданиям.

  ./venv/bin/python manage.py refresh_topic_extra_counts
  ./venv/bin/python manage.py refresh_topic_extra_counts --grade 1
"""

from django.core.management.base import BaseCommand

from knowledge.models import Topic, refresh_topic_extra_task_counts


class Command(BaseCommand):
    help = 'Обновить денормализованный Topic.extra_task_count'

    def add_arguments(self, parser):
        parser.add_argument('--grade', type=int, default=0)

    def handle(self, *args, **options):
        grade = options['grade']
        if grade:
            ids = list(
                Topic.objects.filter(grade_level=grade).values_list('id', flat=True)
            )
            refresh_topic_extra_task_counts(ids)
            self.stdout.write(self.style.SUCCESS(
                f'Обновлено тем класса {grade}: {len(ids)}'
            ))
        else:
            refresh_topic_extra_task_counts()
            total = Topic.objects.count()
            with_extra = Topic.objects.filter(extra_task_count__gt=0).count()
            self.stdout.write(self.style.SUCCESS(
                f'Обновлено все темы: {total}, с доп. заданиями: {with_extra}'
            ))
