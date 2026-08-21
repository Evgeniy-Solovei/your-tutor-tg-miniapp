from django.core.management.base import BaseCommand

from core.models import AppSettings, City, School


CITIES = [
    ('Минск', 'Минская'),
    ('Брест', 'Брестская'),
    ('Витебск', 'Витебская'),
    ('Гомель', 'Гомельская'),
    ('Гродно', 'Гродненская'),
    ('Могилёв', 'Могилёвская'),
    ('Бобруйск', 'Могилёвская'),
    ('Барановичи', 'Брестская'),
    ('Борисов', 'Минская'),
    ('Пинск', 'Брестская'),
    ('Орша', 'Витебская'),
    ('Мозырь', 'Гомельская'),
    ('Солигорск', 'Минская'),
    ('Лида', 'Гродненская'),
    ('Новополоцк', 'Витебская'),
    ('Молодечно', 'Минская'),
    ('Полоцк', 'Витебская'),
    ('Жлобин', 'Гомельская'),
    ('Светлогорск', 'Гомельская'),
    ('Речица', 'Гомельская'),
]


class Command(BaseCommand):
    help = (
        'Демо-геоданные (20 городов). Для полного списка РБ: '
        'python manage.py import_geo_belarus'
    )

    def handle(self, *args, **options):
        settings, _ = AppSettings.objects.get_or_create(pk=1)
        changed = []
        if not settings.welcome_message:
            settings.welcome_message = (
                'Привет! Я бот-репетитор по русскому языку для ЦТ и ЦЭ в Беларуси.\n\n'
                'Каждый день даю задания по слабым темам, считаю статистику '
                'и объясняю ошибки. Начнём?'
            )
            changed.append('welcome_message')
        # Разбор ошибок через конспекты (без LLM) — включён в free по умолчанию
        if not settings.free_ai_explanations_enabled:
            settings.free_ai_explanations_enabled = True
            changed.append('free_ai_explanations_enabled')
        if changed:
            settings.save(update_fields=changed + ['updated_at'])

        created_cities = 0
        for name, region in CITIES:
            city, created = City.objects.get_or_create(
                name=name,
                defaults={'region': region, 'is_active': True},
            )
            if created:
                created_cities += 1
            # по 2 демо-школы на город
            for n in (1, 2):
                School.objects.get_or_create(
                    city=city,
                    name=f'Средняя школа №{n}',
                    defaults={'is_active': True},
                )
            School.objects.get_or_create(
                city=city,
                name=f'Гимназия №1 г. {name}',
                defaults={'is_active': True},
            )

        self.stdout.write(self.style.SUCCESS(
            f'Городов создано: {created_cities}, всего городов: {City.objects.count()}, '
            f'школ: {School.objects.count()}'
        ))
