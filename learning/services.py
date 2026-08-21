"""Сервисы обучения: сессии, адаптивный подбор, проверка ответов."""

import random

from django.db.models import Q, Sum
from django.utils import timezone

from core.services import aget_app_settings
from knowledge.models import ExamVariant, Task, TaskSolution, Topic, VariantTask
from learning.models import DailySession, SessionTask, TaskAttempt, TopicMastery
from students.models import Student


async def get_or_create_daily_session(student: Student) -> DailySession:
    """Создаёт или возвращает ежедневную сессию на сегодня."""
    today = timezone.localdate()
    session, created = await DailySession.objects.aget_or_create(
        student=student,
        session_date=today,
        kind=DailySession.Kind.DAILY,
        defaults={'status': DailySession.Status.PENDING},
    )

    if created or session.status == DailySession.Status.PENDING:
        await _populate_session_tasks(student, session)

    return session


async def create_train_session(student: Student, count: int = 20) -> DailySession:
    """Длинная тренировка — можно решать подряд."""
    total = max(5, min(count, 40))
    session = await DailySession.objects.acreate(
        student=student,
        session_date=timezone.localdate(),
        kind=DailySession.Kind.TRAIN,
        status=DailySession.Status.IN_PROGRESS,
    )
    await _populate_session_tasks(student, session, total_override=total)
    return session


async def create_mistakes_session(student: Student, count: int = 15) -> DailySession:
    """Очередь из тем, где были ошибки."""
    session = await DailySession.objects.acreate(
        student=student,
        session_date=timezone.localdate(),
        kind=DailySession.Kind.MISTAKES,
        status=DailySession.Status.IN_PROGRESS,
    )
    weak = await get_weak_topics(student, limit=10)
    topic_ids = [m.topic_id for m in weak]
    if not topic_ids:
        # нет ошибок — просто тренировка
        await session.adelete()
        return await create_train_session(student, count=count)

    tasks: list[Task] = []
    used: set[int] = set()
    for topic_id in topic_ids:
        if len(tasks) >= count:
            break
        task = await (
            Task.objects.filter(topic_id=topic_id, is_active=True)
            .exclude(id__in=used)
            .order_by('?')
            .afirst()
        )
        if task:
            tasks.append(task)
            used.add(task.id)

    for order, task in enumerate(tasks):
        await SessionTask.objects.acreate(
            session=session,
            task=task,
            purpose=SessionTask.Purpose.WEAK_TOPIC,
            order=order,
        )
    session.tasks_total = len(tasks)
    session.status = (
        DailySession.Status.IN_PROGRESS if tasks else DailySession.Status.COMPLETED
    )
    await session.asave(update_fields=['tasks_total', 'status'])
    return session

async def _populate_session_tasks(
    student: Student,
    session: DailySession,
    total_override: int | None = None,
) -> None:
    settings = await aget_app_settings()
    total = total_override if total_override is not None else settings.daily_session_tasks_count

    has_history = await TopicMastery.objects.filter(
        student=student,
    ).filter(Q(correct_count__gt=0) | Q(wrong_count__gt=0)).aexists()

    selected_tasks: list[tuple[Task, str]] = []
    used_ids: set[int] = set()

    # Новый ученик: только знакомство с темами, без ярлыка «слабая»
    if not has_history:
        new_tasks = await _select_new_tasks(student, total, exclude_ids=used_ids)
        for task in new_tasks:
            selected_tasks.append((task, SessionTask.Purpose.NEW))
            used_ids.add(task.id)
    else:
        weak_count = max(1, int(total * settings.weak_topic_task_ratio))
        review_count = max(1, (total - weak_count) // 2)
        new_count = max(0, total - weak_count - review_count)

        weak_tasks = await _select_tasks_by_mastery(
            student, weak_count, prefer_low=True, exclude_ids=used_ids, only_attempted=True
        )
        for task in weak_tasks:
            selected_tasks.append((task, SessionTask.Purpose.WEAK_TOPIC))
            used_ids.add(task.id)

        # если слабых ещё мало — добираем новыми, не помечая всё как weak
        remain = total - len(selected_tasks)
        if remain > 0:
            review_tasks = await _select_tasks_by_mastery(
                student,
                min(review_count, remain),
                prefer_low=False,
                exclude_ids=used_ids,
                only_attempted=True,
            )
            for task in review_tasks:
                selected_tasks.append((task, SessionTask.Purpose.REVIEW))
                used_ids.add(task.id)

        remain = total - len(selected_tasks)
        if remain > 0:
            new_tasks = await _select_new_tasks(student, remain, exclude_ids=used_ids)
            for task in new_tasks:
                selected_tasks.append((task, SessionTask.Purpose.NEW))
                used_ids.add(task.id)

        # на крайний случай: если mastery пустой по фильтрам — любые задачи как NEW
        if not selected_tasks:
            new_tasks = await _select_new_tasks(student, total, exclude_ids=used_ids)
            for task in new_tasks:
                selected_tasks.append((task, SessionTask.Purpose.NEW))

    await SessionTask.objects.filter(session=session).adelete()

    for order, (task, purpose) in enumerate(selected_tasks):
        await SessionTask.objects.acreate(
            session=session,
            task=task,
            purpose=purpose,
            order=order,
        )

    session.tasks_total = len(selected_tasks)
    session.status = DailySession.Status.IN_PROGRESS if selected_tasks else DailySession.Status.COMPLETED
    await session.asave(update_fields=['tasks_total', 'status'])


async def _get_track_topic_ids(student: Student) -> list[int]:
    """Темы: сначала по классу ученика, потом по треку, иначе весь предмет.

    Так 10 класс не получает банк ЦТ 11, а ЦЭ (grade 11) берёт задания
    открытого банка с grade_level=11, даже если трек ce_11 без своих тем.
    """
    subject_id = student.subject_id
    if student.grade and subject_id:
        by_grade = [
            topic_id
            async for topic_id in Topic.objects.filter(
                is_active=True,
                grade_level=student.grade,
                section__exam_track__subject_id=subject_id,
                section__exam_track__is_active=True,
            ).values_list('id', flat=True)
        ]
        if by_grade:
            return by_grade

    if student.exam_track_id:
        track_ids = [
            topic_id
            async for topic_id in Topic.objects.filter(
                section__exam_track_id=student.exam_track_id,
                is_active=True,
            ).values_list('id', flat=True)
        ]
        if track_ids:
            return track_ids

    if subject_id:
        return [
            topic_id
            async for topic_id in Topic.objects.filter(
                section__exam_track__subject_id=subject_id,
                is_active=True,
            ).values_list('id', flat=True)
        ]
    return []


async def _select_tasks_by_mastery(
    student: Student,
    count: int,
    prefer_low: bool,
    exclude_ids: set[int],
    only_attempted: bool = False,
) -> list[Task]:
    if count <= 0:
        return []

    topic_ids = await _get_track_topic_ids(student)
    if not topic_ids:
        return []

    masteries = TopicMastery.objects.filter(student=student, topic_id__in=topic_ids)
    if only_attempted:
        masteries = masteries.filter(Q(correct_count__gt=0) | Q(wrong_count__gt=0))

    ordered = masteries.order_by('mastery_score' if prefer_low else '-mastery_score')
    priority_topic_ids = []
    async for topic_id in ordered.values_list('topic_id', flat=True)[: count * 3]:
        priority_topic_ids.append(topic_id)

    if not priority_topic_ids:
        priority_topic_ids = topic_ids

    tasks: list[Task] = []
    for topic_id in priority_topic_ids:
        if len(tasks) >= count:
            break
        task = await (
            Task.objects.filter(
                topic_id=topic_id,
                is_active=True,
            )
            .exclude(id__in=exclude_ids | {t.id for t in tasks})
            .order_by('?')
            .afirst()
        )
        if task:
            tasks.append(task)

    # Если тем с заданиями мало (напр. 9 класс — банк изложений в одной теме),
    # добираем ещё заданиями из уже найденных тем / любых тем трека.
    if len(tasks) < count:
        extra = await _fill_tasks_from_topics(
            topic_ids,
            count - len(tasks),
            exclude_ids | {t.id for t in tasks},
        )
        tasks.extend(extra)
    return tasks


async def _select_new_tasks(student: Student, count: int, exclude_ids: set[int]) -> list[Task]:
    if count <= 0:
        return []

    topic_ids = await _get_track_topic_ids(student)
    attempted_topic_ids = []
    async for tid in TopicMastery.objects.filter(student=student).values_list('topic_id', flat=True).aiterator():
        attempted_topic_ids.append(tid)

    new_topic_ids = [tid for tid in topic_ids if tid not in attempted_topic_ids] or topic_ids
    random.shuffle(new_topic_ids)

    tasks: list[Task] = []
    for topic_id in new_topic_ids:
        if len(tasks) >= count:
            break
        task = await (
            Task.objects.filter(topic_id=topic_id, is_active=True)
            .exclude(id__in=exclude_ids | {t.id for t in tasks})
            .order_by('?')
            .afirst()
        )
        if task:
            tasks.append(task)

    if len(tasks) < count:
        extra = await _fill_tasks_from_topics(
            topic_ids,
            count - len(tasks),
            exclude_ids | {t.id for t in tasks},
        )
        tasks.extend(extra)
    return tasks


async def _fill_tasks_from_topics(
    topic_ids: list[int],
    count: int,
    exclude_ids: set[int],
) -> list[Task]:
    if count <= 0 or not topic_ids:
        return []
    qs = Task.objects.filter(topic_id__in=topic_ids, is_active=True).exclude(id__in=exclude_ids)
    return [task async for task in qs.order_by('?')[:count]]


async def get_next_session_task(session: DailySession) -> SessionTask | None:
    return await (
        SessionTask.objects.select_related('task', 'task__topic', 'task__solution')
        .filter(session=session, is_answered=False)
        .order_by('order')
        .afirst()
    )


async def check_task_answer(task: Task, answer_text: str) -> bool:
    """Проверяет ответ по эталону (полностью верно)."""
    from learning.scoring import grade_task_answer

    is_correct, _, _ = await grade_task_answer(task, answer_text)
    return is_correct


async def submit_answer(
    student: Student,
    session_task: SessionTask,
    answer_text: str,
    *,
    time_spent_seconds: int = 0,
) -> TaskAttempt:
    """Сохраняет попытку, обновляет mastery, XP и баллы РИКЗ."""
    from learning.leaderboard import add_weekly_xp
    from learning.scoring import grade_task_answer, recompute_session_scores

    settings = await aget_app_settings()
    task = await Task.objects.aget(pk=session_task.task_id)
    is_correct, points, max_points = await grade_task_answer(task, answer_text)
    spent = max(0, min(int(time_spent_seconds or 0), 60 * 60))

    attempt = await TaskAttempt.objects.acreate(
        student=student,
        task_id=task.id,
        session_task=session_task,
        answer_text=answer_text,
        is_correct=is_correct,
        points_earned=points,
        max_points=max_points,
        time_spent_seconds=spent,
    )

    await _update_topic_mastery(student, task.topic_id, is_correct or points > 0)

    session_task.is_answered = True
    await session_task.asave(update_fields=['is_answered'])

    session = await DailySession.objects.aget(pk=session_task.session_id)
    session.tasks_completed += 1
    earned = 0

    if points > 0:
        # --- ПРАВИЛА НАЧИСЛЕНИЯ XP И ЗАЩИТА ОТ НАКРУТКИ ---

        # 1. Проверка повторного решения той же задачи
        already_solved = await TaskAttempt.objects.filter(
            student=student,
            task_id=task.id,
            is_correct=True,
        ).exclude(id=attempt.id).aexists()

        if already_solved:
            earned = 0
            logger.info('0 XP за повторное решение задачи %s пользователем %s', task.id, student.tg_id)
        else:
            # 2. Начисление XP пропорционально классу/сложности задания
            task_topic = await Topic.objects.select_related('section').filter(id=task.topic_id).afirst()
            task_grade = task_topic.grade_level if task_topic else 11

            if task_grade <= 4:
                base_unit = 2  # Начальная школа (1–4 кл.) — легкие задания
            elif task_grade <= 8:
                base_unit = 5  # Средняя школа (5–8 кл.)
            else:
                base_unit = settings.xp_per_correct_answer or 10  # Старшая школа (9–11 кл.) и ЦТ/ЦЭ

            earned = max(base_unit // max(max_points, 1), 1) * points
            if student.streak_days >= 3 and is_correct:
                earned += settings.streak_bonus_xp

            # 3. Проверка суточного лимита XP (max_daily_xp, по умолчанию 1000 XP/день)
            max_daily = getattr(settings, 'max_daily_xp', 1000) or 1000
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_attempts = await TaskAttempt.objects.filter(
                student=student,
                created_at__gte=today_start,
                is_correct=True,
            ).exclude(id=attempt.id).aaggregate(total=Sum('points_earned'))
            
            today_points = today_attempts.get('total') or 0
            if today_points * base_unit >= max_daily:
                earned = 0
                logger.info('Превышен суточный лимит XP (%s) для %s', max_daily, student.tg_id)

        student.xp += earned
        session.xp_earned += earned

    student.daily_tasks_completed += 1
    await student.asave(update_fields=['xp', 'daily_tasks_completed', 'updated_at'])

    if session.tasks_completed >= session.tasks_total:
        session.status = DailySession.Status.COMPLETED
    await session.asave(update_fields=['tasks_completed', 'xp_earned', 'status'])
    await recompute_session_scores(session)

    if earned > 0:
        # --- ИЗОЛЯЦИЯ ТУРНИРНОГО XP ПО КЛАССАМ ---
        # В турнирную таблицу (weekly_xp) идут только баллы за задания ТЕКУЩЕГО класса ученика (или ЦТ/ЦЭ для 9–11 классов).
        # Задания других классов добавляют XP только в общий профиль ученика.
        student_grade = student.grade or 11
        task_topic = await Topic.objects.select_related('section').filter(id=task.topic_id).afirst()
        task_grade = task_topic.grade_level if task_topic else 11

        is_grade_match = (task_grade == student_grade)
        if is_grade_match:
            await add_weekly_xp(student, earned)
        else:
            logger.info(
                'XP=%s добавлен только в профиль (класс задания %s != класс ученика %s)',
                earned, task_grade, student_grade
            )

    return attempt


async def get_recent_attempts(student: Student, limit: int = 15) -> list[TaskAttempt]:
    return [
        a
        async for a in (
            TaskAttempt.objects.filter(student=student)
            .select_related('task', 'task__topic', 'session_task__session')
            .order_by('-created_at')[:limit]
        )
    ]


async def get_recent_sessions(student: Student, limit: int = 10) -> list[DailySession]:
    return [
        s
        async for s in DailySession.objects.filter(student=student)
        .order_by('-created_at')[:limit]
    ]


async def create_topic_practice_session(student: Student, topic: Topic, count: int = 5) -> DailySession:
    """Разовая практика по выбранной теме."""
    today = timezone.localdate()
    session = await DailySession.objects.acreate(
        student=student,
        session_date=today,
        kind=DailySession.Kind.TRAIN,
        status=DailySession.Status.IN_PROGRESS,
    )

    existing_ids = [
        tid
        async for tid in SessionTask.objects.filter(session=session).values_list('task_id', flat=True)
    ]
    tasks = [
        t
        async for t in Task.objects.filter(topic=topic, is_active=True)
        .exclude(id__in=existing_ids)
        .order_by('?')[:count]
    ]
    start_order = await SessionTask.objects.filter(session=session).acount()
    for i, task in enumerate(tasks):
        await SessionTask.objects.acreate(
            session=session,
            task=task,
            purpose=SessionTask.Purpose.NEW,
            order=start_order + i,
        )
    session.tasks_total = start_order + len(tasks)
    session.status = DailySession.Status.IN_PROGRESS
    await session.asave(update_fields=['tasks_total', 'status'])
    return session


async def create_izlozhenie_session(
    student: Student,
    *,
    task_id: int | None = None,
    count: int = 3,
) -> DailySession:
    """Сессия по официальному сборнику изложений (9 класс)."""
    today = timezone.localdate()
    source = 'Сборник изложений НИО'
    qs = Task.objects.filter(is_active=True, source__startswith=source)
    if task_id:
        qs = qs.filter(id=task_id)
        count = 1

    tasks = [t async for t in qs.order_by('?')[:count]]
    session = await DailySession.objects.acreate(
        student=student,
        session_date=today,
        kind=DailySession.Kind.TRAIN,
        status=(
            DailySession.Status.IN_PROGRESS if tasks else DailySession.Status.COMPLETED
        ),
        tasks_total=len(tasks),
    )
    for i, task in enumerate(tasks):
        await SessionTask.objects.acreate(
            session=session,
            task=task,
            purpose=SessionTask.Purpose.NEW,
            order=i,
        )
    return session


async def list_izlozhenie_catalog(*, q: str = '', limit: int = 200) -> list[dict]:
    from knowledge.izlozhenie import parse_izlozhenie_question

    qs = Task.objects.filter(
        is_active=True,
        source__startswith='Сборник изложений НИО',
    ).select_related('topic').order_by('id')
    items: list[dict] = []
    async for task in qs:
        parsed = parse_izlozhenie_question(task.question)
        title = parsed.title
        if q and q.lower() not in title.lower():
            continue
        items.append(
            {
                'id': task.id,
                'title': title,
                'word_count': parsed.word_count,
                'topic_name': task.topic.name,
            }
        )
        if len(items) >= limit:
            break
    return items


async def _update_topic_mastery(student: Student, topic_id: int, is_correct: bool) -> None:
    mastery, _ = await TopicMastery.objects.aget_or_create(
        student=student,
        topic_id=topic_id,
        defaults={'last_attempt_at': timezone.now()},
    )
    if is_correct:
        mastery.correct_count += 1
    else:
        mastery.wrong_count += 1
    mastery.last_attempt_at = timezone.now()
    mastery.recalculate_score()
    await mastery.asave()


async def get_weak_topics(student: Student, limit: int = 5) -> list[TopicMastery]:
    topic_ids = await _get_track_topic_ids(student)
    return [
        m
        async for m in TopicMastery.objects.filter(
            student=student,
            topic_id__in=topic_ids,
            wrong_count__gt=0,
        )
        .select_related('topic')
        .order_by('mastery_score')[:limit]
    ]


async def build_ai_context(task: Task) -> str:
    """Собирает контекст из конспекта и фрагментов учебника для ИИ."""
    from knowledge.models import TextbookFragment, TopicSummary

    parts = []
    try:
        summary = await TopicSummary.objects.aget(topic_id=task.topic_id)
        parts.append(f'Конспект: {summary.content}')
        if summary.key_points:
            parts.append(f'Ключевые правила: {summary.key_points}')
    except TopicSummary.DoesNotExist:
        pass

    async for fragment in TextbookFragment.objects.filter(topic_id=task.topic_id)[:3]:
        parts.append(f'Учебник ({fragment.title}): {fragment.content[:1500]}')

    try:
        solution = await TaskSolution.objects.aget(task_id=task.id)
        parts.append(f'Правильный ответ: {solution.correct_answer}')
        parts.append(f'Разбор: {solution.explanation}')
    except TaskSolution.DoesNotExist:
        pass

    return '\n\n'.join(parts)


async def create_exam_simulator_session(
    student: Student,
    *,
    variant_id: int | None = None,
) -> DailySession:
    """Создаёт полноразмерный экзаменационный билет ЦТ/ЦЭ из 40 вопросов на 180 минут."""
    today = timezone.localdate()

    await (
        DailySession.objects.filter(
            student=student,
            status=DailySession.Status.IN_PROGRESS,
            kind=DailySession.Kind.EXAM,
        )
        .aupdate(status=DailySession.Status.COMPLETED)
    )

    tasks: list[Task] = []
    variant = None
    if variant_id:
        try:
            variant = await ExamVariant.objects.aget(id=variant_id, is_active=True)
            async for vt in VariantTask.objects.filter(variant=variant).select_related('task').order_by('order'):
                tasks.append(vt.task)
        except ExamVariant.DoesNotExist:
            pass

    if len(tasks) < 40:
        topic_ids = await _get_track_topic_ids(student)
        existing_ids = {t.id for t in tasks}

        part_a_qs = Task.objects.filter(
            is_active=True,
            answer_format__in=[
                Task.AnswerFormat.SINGLE_CHOICE,
                Task.AnswerFormat.MULTIPLE_CHOICE,
            ],
        ).exclude(id__in=existing_ids)
        if topic_ids:
            part_a_qs = part_a_qs.filter(topic_id__in=topic_ids)
        part_a = [t async for t in part_a_qs.order_by('?')[: 30 - len(tasks)]]
        tasks.extend(part_a)

        existing_ids = {t.id for t in tasks}
        part_b_qs = Task.objects.filter(
            is_active=True,
            answer_format=Task.AnswerFormat.SHORT_TEXT,
        ).exclude(id__in=existing_ids)
        if topic_ids:
            part_b_qs = part_b_qs.filter(topic_id__in=topic_ids)
        part_b = [t async for t in part_b_qs.order_by('?')[: 40 - len(tasks)]]
        tasks.extend(part_b)

        if len(tasks) < 40:
            existing_ids = {t.id for t in tasks}
            extra = [
                t async for t in Task.objects.filter(is_active=True).exclude(id__in=existing_ids).order_by('?')[: 40 - len(tasks)]
            ]
            tasks.extend(extra)

    session = await DailySession.objects.acreate(
        student=student,
        session_date=today,
        kind=DailySession.Kind.EXAM,
        exam_variant=variant,
        status=DailySession.Status.IN_PROGRESS,
        tasks_total=len(tasks),
        time_limit_seconds=10800,  # 180 минут
    )

    for order, task in enumerate(tasks):
        await SessionTask.objects.acreate(
            session=session,
            task=task,
            purpose=SessionTask.Purpose.NEW,
            order=order,
        )

    return session


async def submit_exam_simulator(
    student: Student,
    session: DailySession,
    answers: list[dict],
    time_spent_seconds: int = 0,
) -> dict:
    """Проверяет все вопросы симулятора ЦТ/ЦЭ, переводит балл по РИКЗ и даёт итоговый бланк."""
    from learning.scoring import grade_task_answer, primary_to_test_score

    answer_map = {}
    for item in answers:
        if isinstance(item, dict) and 'session_task_id' in item:
            try:
                st_id = int(item['session_task_id'])
                answer_map[st_id] = (item.get('answer_text') or '').strip()
            except (ValueError, TypeError):
                pass

    primary_score = 0
    max_primary = 0
    results = []

    session_tasks = [
        st
        async for st in SessionTask.objects.filter(session=session)
        .select_related('task')
        .order_by('order')
    ]
    for st in session_tasks:
        user_answer = answer_map.get(st.id, '')
        is_correct, points, max_pts = await grade_task_answer(st.task, user_answer)
        primary_score += points
        max_primary += max_pts

        await TaskAttempt.objects.acreate(
            student=student,
            task=st.task,
            session_task=st,
            answer_text=user_answer,
            is_correct=is_correct,
            points_earned=points,
            max_points=max_pts,
            time_spent_seconds=0,
        )
        st.is_answered = True
        await st.asave(update_fields=['is_answered'])

        task_num_str = f'B{(st.order + 1) - 30}' if (st.order + 1) > 30 else f'A{st.order + 1}'
        results.append({
            'session_task_id': st.id,
            'order': st.order + 1,
            'task_number': task_num_str,
            'question': st.task.question,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'points_earned': points,
            'max_points': max_pts,
        })

    test_score = await primary_to_test_score(primary_score, exam_track_id=student.exam_track_id)

    session.tasks_completed = len(session_tasks)
    session.primary_score = primary_score
    session.max_primary = max_primary
    session.test_score = test_score
    session.status = DailySession.Status.COMPLETED
    session.time_spent_seconds = max(0, int(time_spent_seconds or 0))
    session.completed_at = timezone.now()
    await session.asave()

    if test_score is None:
        level = 'Не определён'
    elif test_score >= 80:
        level = 'Высокий уровень (8–10 баллов)'
    elif test_score >= 60:
        level = 'Достаточный уровень (6–7 баллов)'
    elif test_score >= 40:
        level = 'Средний уровень (4–5 баллов)'
    else:
        level = 'Удовлетворительный уровень (1–3 балла)'

    from learning.leaderboard import record_student_activity
    await record_student_activity(student, test_score=test_score or 0, primary_score=primary_score)

    return {
        'session_id': session.id,
        'test_score': test_score or 0,
        'primary_score': primary_score,
        'max_primary': max_primary,
        'tasks_total': len(session_tasks),
        'time_spent_seconds': session.time_spent_seconds,
        'level_description': level,
        'results': results,
    }
