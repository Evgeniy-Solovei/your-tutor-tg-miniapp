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
    if task.answer_format == Task.AnswerFormat.TEXT:
        try:
            solution = await TaskSolution.objects.aget(task_id=task.id)
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

    correct_set: set[str] = set()
    try:
        solution = await TaskSolution.objects.aget(task_id=task.id)
        correct_set = parse_token_set(solution.correct_answer)
    except TaskSolution.DoesNotExist:
        solution = None

    if not correct_set and task.answer_format in (
        Task.AnswerFormat.SINGLE_CHOICE,
        Task.AnswerFormat.MULTIPLE_CHOICE,
    ):
        async for opt in TaskOption.objects.filter(task_id=task.id, is_correct=True):
            # предпочитаем номер варианта, если есть order
            token = str(opt.order) if opt.order else normalize_answer(opt.text)
            correct_set.add(token)

    # Также принимаем ответ текстом варианта
    if student_set and correct_set:
        # если ученик ответил текстом опций — сопоставим с order
        option_map = {}
        async for opt in TaskOption.objects.filter(task_id=task.id):
            option_map[normalize_answer(opt.text)] = str(opt.order) if opt.order else normalize_answer(opt.text)
        mapped = set()
        for token in student_set:
            mapped.add(option_map.get(token, token))
        student_set = mapped

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
    """Пересчитать сумму первичных и тестовый балл сессии."""
    from learning.models import TaskAttempt
    from students.models import Student

    primary = 0
    max_primary = 0
    async for attempt in TaskAttempt.objects.filter(session_task__session=session):
        primary += attempt.points_earned
        max_primary += attempt.max_points

    student = await Student.objects.aget(pk=session.student_id)
    test = await primary_to_test_score(primary, exam_track_id=student.exam_track_id)

    # Тестовый — перевод суммы первичных по шкале РИКЗ (для куска теста — ориентир).
    session.primary_score = primary
    session.max_primary = max_primary
    session.test_score = test
    await session.asave(update_fields=['primary_score', 'max_primary', 'test_score'])
