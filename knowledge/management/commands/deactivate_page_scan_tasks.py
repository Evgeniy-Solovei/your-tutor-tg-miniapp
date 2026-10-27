"""Устарело: страницы 1 класса — нормальные задания с картинкой.

Используй: python manage.py fix_grade1_page_tasks
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Устарело — см. fix_grade1_page_tasks'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                'Команда устарела. Запусти: python manage.py fix_grade1_page_tasks'
            )
        )
