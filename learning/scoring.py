"""Подсчёт первичных и тестовых баллов по правилам РИКЗ."""

from __future__ import annotations

import re

from knowledge.models import ScoreScale, ScoreScaleRow, Task, TaskOption, TaskSolution
from knowledge.score_tables import RU_BE_2025_SCALE


def normalize_answer(value: str) -> str:
    value = (value or '').strip().lower().replace('ё', 'е')
    value = re.sub(r'\s*,\s*', ',', value)
    value = re.sub(r'\s+', ' ', value)
    return value


def parse_token_set(value: str) -> set[str]:
    value = normalize_answer(value)
    if not value:
        return set()
    if re.fullmatch(r'\d+(?:,\d+)*', value):
        return set(value.split(','))
    # несколько токенов через запятую
    if ',' in value:
        return {normalize_answer(p) for p in value.split(',') if p.strip()}
    return {value}


def default_scoring_scheme(answer_format: str) -> str:
    if answer_format == Task.AnswerFormat.MULTIPLE_CHOICE:
        return Task.ScoringScheme.PARTIAL_2
    if answer_format == Task.AnswerFormat.SINGLE_CHOICE:
        return Task.ScoringScheme.BINARY_1
    # краткий ответ части B часто 0/2
    return Task.ScoringScheme.BINARY_2


def max_points_for_scheme(scheme: str) -> int:
    if scheme == Task.ScoringScheme.BINARY_1:
        return 1
    return 2


def points_from_sets(student: set[str], correct: set[str], scheme: str) -> int:
    if not correct:
        return 0
    if scheme == Task.ScoringScheme.BINARY_1:
        return 1 if student == correct else 0
    if scheme == Task.ScoringScheme.BINARY_2:
        return 2 if student == correct else 0
    # PARTIAL_2: одна ошибка (симметрическая разность размера 1) → 1 балл
    errors = len(student.symmetric_difference(correct))
    if errors == 0:
        return 2
    if errors == 1:
        return 1
    return 0


async def grade_task_answer(task: Task, answer_text: str) -> tuple[bool, int, int]:
    """
    Возвращает (is_correct, points_earned, max_points).
    is_correct=True если набраны все возможные баллы.
    """
    scheme = task.scoring_scheme or default_scoring_scheme(task.answer_format)
    max_points = max_points_for_scheme(scheme)

    # Длинный текстовый ответ (изложение): пока без автопроверки смысла —
    # оцениваем по объёму как тренировку (эталон хранится для разбора/ИИ).
    solution = task._state.fields_cache.get('solution')
    if solution is None:
        try:
            solution = await TaskSolution.objects.aget(task_id=task.id)
        except TaskSolution.DoesNotExist:
            solution = None

    if task.answer_format == Task.AnswerFormat.TEXT:
        try:
            if solution is None:
                raise TaskSolution.DoesNotExist
            etalon_words = len((solution.correct_answer or '').split())
        except TaskSolution.DoesNotExist:
            solution = None
            etalon_words = 0
        if etalon_words >= 80:
            student_words = len((answer_text or '').split())
            if student_words < 40:
                return False, 0, max_points
            if student_words >= int(etalon_words * 0.55):
                return True, max_points, max_points
            return False, 1 if max_points >= 2 else 0, max_points

    student_set = parse_token_set(answer_text)

    # Для заданий с вариантами ответов (SINGLE_CHOICE / MULTIPLE_CHOICE)
    # эталоном являются варианты с is_correct=True, а также solution.correct_answer.
    if task.answer_format in (
        Task.AnswerFormat.SINGLE_CHOICE,
        Task.AnswerFormat.MULTIPLE_CHOICE,
    ):
        options = getattr(task, '_prefetched_objects_cache', {}).get('options')
        if options is None:
            options = [opt async for opt in TaskOption.objects.filter(task_id=task.id)]

        if options:
            order_tokens = {str(opt.order) for opt in options if opt.order}

            # 1. Эталонные номера вариантов из базы (is_correct=True)
            correct_set: set[str] = {str(opt.order) for opt in options if opt.is_correct and opt.order}

            # 2. Если в TaskOption не проставлен is_correct, берём из solution.correct_answer
            if not correct_set and solution and solution.correct_answer:
                parsed_sol = parse_token_set(solution.correct_answer)
                if parsed_sol.issubset(order_tokens):
                    correct_set = parsed_sol
                else:
                    for opt in options:
                        if (
                            opt.text.strip() == solution.correct_answer.strip()
                            or normalize_answer(opt.text) == normalize_answer(solution.correct_answer)
                        ):
                            if opt.order:
                                correct_set.add(str(opt.order))

            # 3. Приводим ответ ученика к номерам вариантов:
            parsed_student = parse_token_set(answer_text)
            if parsed_student and parsed_student.issubset(order_tokens):
                # Ответ уже передан как номера вариантов (например, '1' или '1,3')
                student_set = parsed_student
            else:
                # Введён текст варианта: сначала ищем точное совпадение (с учётом регистра),
                # затем нормализованное
                matched_orders = set()
                raw_ans = (answer_text or '').strip()
                norm_ans = normalize_answer(answer_text)

                for opt in options:
                    if opt.text.strip() == raw_ans:
                        matched_orders.add(str(opt.order))

                if not matched_orders:
                    for opt in options:
                        if normalize_answer(opt.text) == norm_ans:
                            matched_orders.add(str(opt.order))

                if matched_orders:
                    student_set = matched_orders
                else:
                    student_set = parsed_student

            points = points_from_sets(student_set, correct_set, scheme)
            is_correct = points == max_points and max_points > 0
            return is_correct, points, max_points

    # Для текстовых ответов или задач без вариантов:
    correct_set: set[str] = set()
    if solution and solution.correct_answer:
        correct_set = parse_token_set(solution.correct_answer)

    points = points_from_sets(student_set, correct_set, scheme)
    is_correct = points == max_points and max_points > 0
    return is_correct, points, max_points


async def primary_to_test_score(
    primary: int,
    *,
    exam_track_id: int | None = None,
    year: int | None = None,
) -> int | None:
    """Перевод первичного балла в тестовый по шкале РИКЗ."""
    qs = ScoreScale.objects.all()
    if exam_track_id:
        qs = qs.filter(exam_track_id=exam_track_id)
    if year:
        qs = qs.filter(year=year)
    else:
        qs = qs.filter(is_current=True)

    scale = await qs.order_by('-year').afirst()
    if scale:
        row = await ScoreScaleRow.objects.filter(
            scale=scale, primary_score=primary
        ).afirst()
        if row:
            return row.test_score
        # clamp to max
        if primary >= scale.max_primary:
            last = await (
                ScoreScaleRow.objects.filter(scale=scale)
                .order_by('-primary_score')
                .afirst()
            )
            return last.test_score if last else None
        return None

    # fallback на захардкоженную таблицу 2025
    if primary in RU_BE_2025_SCALE:
        return RU_BE_2025_SCALE[primary]
    if primary > 80:
        return 100
    return RU_BE_2025_SCALE.get(max(0, primary))


async def recompute_session_scores(session) -> None:
    """Пересчитать сумму первичных и тестовый балл сессии по лучшей попытке на каждое задание."""
    from learning.models import TaskAttempt
    from students.models import Student

    best_attempts: dict[int, dict[str, int]] = {}
    async for att in TaskAttempt.objects.filter(session_task__session=session).order_by('created_at'):
        st_id = att.session_task_id
        if st_id not in best_attempts or att.points_earned > best_attempts[st_id]['points']:
            best_attempts[st_id] = {
                'points': att.points_earned,
                'max_points': att.max_points,
            }

    primary = sum(x['points'] for x in best_attempts.values())
    max_primary = sum(x['max_points'] for x in best_attempts.values())

    cached_student = getattr(session, '_state', None) and session._state.fields_cache.get('student')
    if cached_student:
        track_id = cached_student.exam_track_id
    else:
        student = await Student.objects.aget(pk=session.student_id)
        track_id = student.exam_track_id

    test = await primary_to_test_score(primary, exam_track_id=track_id)

    # Тестовый — перевод суммы первичных по шкале РИКЗ (для куска теста — ориентир).
    session.primary_score = primary
    session.max_primary = max_primary
    session.test_score = test
    await session.asave(update_fields=['primary_score', 'max_primary', 'test_score'])
