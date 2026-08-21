"""
Обновить условия/опции ЦТ из vision TASKS JSON (ключи из KEYS.json).

  ./venv/bin/python manage.py update_ct_vision_tasks \\
      --tasks materials/russian/11_klass/variants/_ocr_text/CT_rus_2003_v1_TASKS.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import Task, TaskOption, TaskSolution

KEYS_DIR = Path('materials/russian/11_klass/variants/_ocr_text')


class Command(BaseCommand):
    help = 'Обновить задания ЦТ из vision TASKS JSON + KEYS'

    def add_arguments(self, parser):
        parser.add_argument('--tasks', type=str, required=True)
        parser.add_argument(
            '--keys',
            type=str,
            default='',
            help='Путь к KEYS.json (по умолчанию CT_rus_{year}_KEYS.json)',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        tasks_path = Path(options['tasks'])
        if not tasks_path.exists():
            raise CommandError(f'Нет файла: {tasks_path}')

        data = json.loads(tasks_path.read_text(encoding='utf-8'))
        exam = data.get('exam', 'ct')
        year = int(data['year'])
        variant = int(data['variant'])
        tasks = data['tasks']
        if not tasks:
            raise CommandError('Пустой список tasks')

        keys_path = Path(options['keys']) if options['keys'] else KEYS_DIR / f'CT_rus_{year}_KEYS.json'
        if not keys_path.exists():
            raise CommandError(f'Нет ключей: {keys_path}')
        keys_all = json.loads(keys_path.read_text(encoding='utf-8'))
        vkeys = keys_all.get(str(variant)) or keys_all.get(variant)
        if not vkeys:
            raise CommandError(f'Нет ключей варианта {variant} в {keys_path}')

        label = 'ЦТ'
        prefix = f'ЦТ OCR / {label} {year}'
        # строго «вариант N /» чтобы не цеплять вариант 10 при N=1
        source_base = f'{prefix} / вариант {variant} / '

        updated = 0
        missing_src = []
        missing_key = []

        with transaction.atomic():
            for item in tasks:
                code = item['code']
                stem = (item.get('stem') or '').strip()
                opts = [str(o).strip() for o in (item.get('options') or [])]
                answer = vkeys.get(code)
                if not answer:
                    missing_key.append(code)
                    continue

                source = f'{source_base}{code}'
                task = Task.objects.filter(source=source).first()
                if not task:
                    # fallback без лишнего пробела / кириллица A→А
                    alt = source.replace('А', 'A')
                    task = Task.objects.filter(source=alt).first()
                if not task:
                    missing_src.append(source)
                    continue

                answer_norm = ','.join(
                    x.strip() for x in str(answer).replace(' ', '').split(',') if x.strip()
                )
                need_mc = bool(re.fullmatch(r'(?:\d(?:,\d)*)', answer_norm)) and len(opts) >= 2

                question = f'[{label} {year} · вар.{variant} · {code}] {stem}'[:4000]

                if options['dry_run']:
                    self.stdout.write(f'DRY {source}: opts={len(opts)} ans={answer_norm}')
                    updated += 1
                    continue

                if need_mc:
                    task.question = question
                    task.answer_format = Task.AnswerFormat.MULTIPLE_CHOICE
                    task.scoring_scheme = Task.ScoringScheme.PARTIAL_2
                    task.is_active = True
                    task.save(update_fields=['question', 'answer_format', 'scoring_scheme', 'is_active'])

                    task.options.all().delete()
                    correct = {int(x) for x in answer_norm.split(',') if x.isdigit()}
                    max_opt = max(correct) if correct else len(opts)
                    while len(opts) < max_opt:
                        opts.append(f'(вариант {len(opts) + 1})')
                    for idx, label_opt in enumerate(opts[: max(5, max_opt)], start=1):
                        TaskOption.objects.create(
                            task=task,
                            text=f'{idx}) {label_opt}'[:500],
                            is_correct=idx in correct,
                            order=idx,
                        )
                else:
                    body = stem
                    if opts:
                        body = stem + '\n' + '\n'.join(f'{j}) {o}' for j, o in enumerate(opts, 1))
                    task.question = f'[{label} {year} · вар.{variant} · {code}] {body}'[:4000]
                    task.answer_format = Task.AnswerFormat.TEXT
                    task.scoring_scheme = Task.ScoringScheme.BINARY_2
                    task.is_active = True
                    task.save(update_fields=['question', 'answer_format', 'scoring_scheme', 'is_active'])
                    task.options.all().delete()

                sol, _ = TaskSolution.objects.get_or_create(task=task)
                sol.correct_answer = answer_norm
                sol.explanation = (
                    f'Ключ {label} {year}, вариант {variant}, {code}: {answer_norm} '
                    f'(vision update {tasks_path.name})'
                )
                sol.save(update_fields=['correct_answer', 'explanation'])
                updated += 1

            if options['dry_run']:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(f'Обновлено: {updated}/{len(tasks)}'))
        if missing_src:
            self.stdout.write(self.style.WARNING(f'Нет в БД ({len(missing_src)}): {missing_src[:5]}…'))
        if missing_key:
            self.stdout.write(self.style.WARNING(f'Нет ключа: {missing_key}'))
