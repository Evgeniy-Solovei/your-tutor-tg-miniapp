from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Полная инициализация: гео, предметы, треки, конспекты'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-bank',
            action='store_true',
            help='Также переимпортировать открытый банк из materials/russian/11_klass/',
        )

    def handle(self, *args, **options):
        call_command('seed_geo')
        call_command('seed_exam_tracks')
        call_command('import_geo_belarus')
        call_command('enrich_summaries')
        call_command('import_rikz_bank')
        self.stdout.write(self.style.SUCCESS('setup_project завершён'))
