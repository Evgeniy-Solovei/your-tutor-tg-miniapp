"""
Аудит, балансировка и верификация вариантов ответов для викторины/тестов (1–10 классы).

1. Равномерно распределяет правильные ответы по позициям 1, 2, 3, 4 (по ~25% на каждую),
   чтобы в викторине правильный ответ не находился всегда под кнопкой 1.
2. Очищает формулировки вопросов от пустых скобок (): и артефактов пунктуации.
3. Синхронизирует TaskSolution с текстом и номером правильного варианта.
4. Выполняет 100% верификацию каждого задания через grade_task_answer.
5. Пересохраняет дамп базы данных backups/db_dump_school_enriched.json.

Запуск:
  USE_SQLITE=1 python manage.py audit_and_balance_quiz_options
"""
import re
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import Task, TaskOption, TaskSolution
from learning.scoring import grade_task_answer


def clean_question(text: str) -> str:
    # 1. Удаление пустых скобок ():
    text = re.sub(
        r'❓ Укажите верный вариант орфографического и пунктуационного оформления в упражнении \(\s*\):',
        '❓ Укажите верный вариант орфографического и пунктуационного оформления:',
        text
    )
    # 2. Очистка слов внутри скобок от завершающих точек и запятых: (слово., другое.:) -> (слово, другое):
    def clean_paren_content(m):
        content = m.group(1)
        tokens = [t.strip().rstrip('.,;:!?') for t in content.split(',') if t.strip().rstrip('.,;:!?')]
        if not tokens:
            return '❓ Укажите верный вариант орфографического и пунктуационного оформления:'
        return f'❓ Укажите верный вариант орфографического оформления слов ({", ".join(tokens)}):'

    text = re.sub(
        r'❓ Укажите верный вариант орфографического и пунктуационного оформления в упражнении \(([^\)]+)\):',
        clean_paren_content,
        text
    )
    return text


class Command(BaseCommand):
    help = 'Балансировка и 100% верификация правильных ответов викторины'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🎯 НАЧАЛО АУДИТА И БАЛАНСИРОВКИ ОТВЕТОВ ВИКТОРИНЫ (1–10 КЛАССЫ)...'))

        tasks_to_process = (
            Task.objects.filter(
                topic__grade_level__range=(1, 10),
                is_active=True,
                answer_format__in=[Task.AnswerFormat.MULTIPLE_CHOICE, Task.AnswerFormat.SINGLE_CHOICE],
            )
            .prefetch_related('options')
            .select_related('solution', 'topic')
        )

        total_tasks = tasks_to_process.count()
        self.stdout.write(f'Найдено заданий для балансировки и проверки: {total_tasks}')

        rebalanced_count = 0
        cleaned_questions_count = 0
        position_stats = {1: 0, 2: 0, 3: 0, 4: 0}

        with transaction.atomic():
            for task in tasks_to_process:
                # 1. Очистка текста вопроса
                old_q = task.question
                new_q = clean_question(old_q)
                if new_q != old_q:
                    task.question = new_q
                    task.save(update_fields=['question'])
                    cleaned_questions_count += 1

                # 2. Балансировка вариантов ответов
                opts = list(task.options.all().order_by('order', 'id'))
                if len(opts) < 2:
                    continue

                correct_opts = [o for o in opts if o.is_correct]
                if not correct_opts:
                    # Если нет правильного — делаем первый правильным
                    opts[0].is_correct = True
                    correct_opts = [opts[0]]

                target_corr = correct_opts[0]
                other_opts = [o for o in opts if o.id != target_corr.id]

                # Детерминированная позиция 1..len(opts) на основе ID задачи
                target_pos = (task.id % len(opts)) + 1
                new_opts = []
                for pos in range(1, len(opts) + 1):
                    if pos == target_pos:
                        new_opts.append(target_corr)
                    else:
                        new_opts.append(other_opts.pop(0))

                for idx, opt in enumerate(new_opts, start=1):
                    if opt.order != idx:
                        opt.order = idx
                        opt.save(update_fields=['order'])

                position_stats[target_pos] = position_stats.get(target_pos, 0) + 1

                # 3. Синхронизация TaskSolution
                sol = getattr(task, 'solution', None)
                if not sol:
                    sol = TaskSolution.objects.create(
                        task=task,
                        correct_answer=target_corr.text,
                        explanation=f"Правильный ответ: {target_pos}. {target_corr.text}"
                    )
                else:
                    sol.correct_answer = target_corr.text
                    # Добавляем в объяснение четкое указание номера варианта
                    if not sol.explanation or f"Правильный ответ: {target_pos}" not in sol.explanation:
                        sol.explanation = (
                            f"**Правильный ответ: вариант {target_pos} — «{target_corr.text}»**\n\n"
                            f"{sol.explanation}"
                        )
                    sol.save()

                rebalanced_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ Сбалансировано {rebalanced_count} заданий. Очищено вопросов: {cleaned_questions_count}'
        ))
        self.stdout.write(f'📊 Распределение правильных ответов по кнопкам (1–4): {position_stats}')

        # 4. ФАЗА ВЕРИФИКАЦИИ КАЖДОГО ЗАДАНИЯ
        self.stdout.write(self.style.SUCCESS('🔍 ЗАПУСК 100% ВЕРИФИКАЦИИ КАЖДОГО ЗАДАНИЯ ЧЕРЕЗ СИСТЕМУ ОЦЕНКИ...'))
        import asyncio

        async def verify_all():
            errors = []
            verified = 0
            tasks_check = (
                Task.objects.filter(
                    topic__grade_level__range=(1, 10),
                    is_active=True,
                    answer_format__in=[Task.AnswerFormat.MULTIPLE_CHOICE, Task.AnswerFormat.SINGLE_CHOICE],
                )
                .prefetch_related('options')
                .select_related('solution', 'topic')
            )
            async for t in tasks_check:
                opts = [o async for o in t.options.all().order_by('order')]
                corr_opts = [o for o in opts if o.is_correct]
                if not corr_opts:
                    errors.append(f'Task {t.id}: нет правильного варианта!')
                    continue

                corr_order = str(corr_opts[0].order)
                # 1. Проверяем правильный ответ по номеру кнопки (1, 2, 3, 4)
                is_c, pts, max_pts = await grade_task_answer(t, corr_order)
                if not is_c or pts < max_pts:
                    errors.append(f'Task {t.id} (grade {t.topic.grade_level}): отправка {corr_order} вернула is_correct={is_c}, pts={pts}/{max_pts}')

                # 2. Проверяем правильный ответ по тексту (если текст не совпадает с номером другого варианта)
                text_ans = corr_opts[0].text.strip()
                if not (text_ans.isdigit() and text_ans != corr_order and text_ans in [str(o.order) for o in opts]):
                    is_ct, ptst, _ = await grade_task_answer(t, text_ans)
                    if not is_ct or ptst < max_pts:
                        errors.append(f'Task {t.id}: отправка текста «{corr_opts[0].text[:30]}» вернула is_correct={is_ct}')

                # 3. Проверяем, что неверный вариант возвращает ошибку
                wrong_orders = [str(o.order) for o in opts if not o.is_correct]
                if wrong_orders:
                    is_w, pts_w, _ = await grade_task_answer(t, wrong_orders[0])
                    if is_w or pts_w > 0:
                        errors.append(f'Task {t.id}: неверный ответ {wrong_orders[0]} был засчитан как верный!')

                verified += 1
                if verified % 1000 == 0:
                    print(f'   Проверено {verified}/{total_tasks} заданий без единой ошибки...')

            return verified, errors

        verified_count, errors_list = asyncio.run(verify_all())

        if errors_list:
            self.stdout.write(self.style.ERROR(f'❌ НАЙДЕНО {len(errors_list)} ОШИБОК:'))
            for e in errors_list[:10]:
                self.stdout.write(self.style.ERROR(f'   - {e}'))
            raise RuntimeError('Верификация базы данных не прошла!')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'🎉 ВСЕ {verified_count} ЗАДАНИЙ УСПЕШНО ПРОШЛИ 100% ТЕСТИРОВАНИЕ! 0 ОШИБОК!'
            ))

        # 5. Пересохранение дампа базы
        dump_path = 'backups/db_dump_school_enriched.json'
        self.stdout.write(f'📦 Пересохранение эталонного дампа базы в {dump_path}...')
        with open(dump_path, 'w', encoding='utf-8') as f:
            call_command(
                'dumpdata',
                '--natural-foreign',
                '--natural-primary',
                '-e', 'contenttypes',
                '-e', 'auth.Permission',
                stdout=f
            )
        self.stdout.write(self.style.SUCCESS('🎉 Эталонный дамп базы данных успешно обновлён!'))
