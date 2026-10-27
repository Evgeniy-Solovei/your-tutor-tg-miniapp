"""Убирает «Упражнение N…» / «стр. N» из Task.question по всей БД."""

from django.core.management.base import BaseCommand

from knowledge.models import Task
from knowledge.question_cleanup import clean_student_question


class Command(BaseCommand):
    help = 'Чистит номера упражнений и страниц из текста заданий (question)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--batch', type=int, default=500)

    def handle(self, *args, **options):
        dry = options['dry_run']
        batch = max(50, options['batch'])
        qs = Task.objects.all().only('id', 'question').order_by('id')
        total = qs.count()
        changed = 0
        scanned = 0
        buf = []

        for task in qs.iterator(chunk_size=batch):
            scanned += 1
            old = task.question or ''
            new = clean_student_question(old)
            if new == old:
                continue
            changed += 1
            if dry:
                if changed <= 5:
                    self.stdout.write(f'--- #{task.id}')
                    self.stdout.write(f'was: {old[:120]!r}')
                    self.stdout.write(f'now: {new[:120]!r}')
                continue
            task.question = new
            buf.append(task)
            if len(buf) >= batch:
                Task.objects.bulk_update(buf, ['question'])
                buf.clear()
                self.stdout.write(f'  … {scanned}/{total}, изменено {changed}')

        if not dry and buf:
            Task.objects.bulk_update(buf, ['question'])

        self.stdout.write(self.style.SUCCESS(
            f'{"[dry] " if dry else ""}просмотрено {scanned}, изменено {changed}'
        ))
