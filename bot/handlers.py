"""Обработчики Telegram-бота."""

import logging
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutor_bot.settings')
django.setup()

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from django.utils import timezone

from bot.keyboards import (
    after_answer_keyboard,
    children_pick_keyboard,
    main_menu_keyboard,
    miniapp_inline_keyboard,
    multi_choice_keyboard,
    parent_menu_keyboard,
    rating_scope_keyboard,
    topics_keyboard,
)
from bot.states import DailyPractice, ParentFlow, Registration, TopicPractice
from core.models import AppSettings
from core.services import student_can_practice, student_can_request_ai
from knowledge.models import Task, TaskOption, Topic
from learning.ai_service import explain_mistake
from learning.leaderboard import get_leaderboard
from learning.services import (
    create_mistakes_session,
    create_topic_practice_session,
    create_train_session,
    get_next_session_task,
    get_or_create_daily_session,
    get_recent_attempts,
    get_recent_sessions,
    get_weak_topics,
    submit_answer,
)
from students.models import Parent, ParentChildLink, Student
from students.parent_service import (
    build_parent_report,
    get_active_invite,
    get_or_create_parent,
    issue_parent_invite,
    link_parent_by_code,
    list_children,
)

router = Router()
logger = logging.getLogger(__name__)


def _is_cancel(text: str | None) -> bool:
    return (text or '').strip() == '❌ Отмена'


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    student = await Student.objects.filter(tg_id=message.from_user.id).afirst()
    settings = await AppSettings.aget_settings()
    welcome = settings.welcome_message or (
        'Привет! Подготовка к ЦТ/ЦЭ и аттестату по русскому (Беларусь).\n'
        'Практика и статистика — в мини-приложении.'
    )

    if student and student.registration_completed:
        await message.answer(welcome, reply_markup=main_menu_keyboard())
        mini_kb = miniapp_inline_keyboard()
        if mini_kb:
            await message.answer('Мини-приложение:', reply_markup=mini_kb)
        return

    mini_kb = miniapp_inline_keyboard()
    text = (
        f'{welcome}\n\n'
        'Регистрация только в мини-приложении: имя, класс, цель, предмет, город и школа.\n'
        'Нажми кнопку ниже — и заполни форму там.'
    )
    if mini_kb:
        await message.answer(text, reply_markup=mini_kb)
    else:
        await message.answer(
            text + '\n\n⚠️ URL мини-приложения не задан. '
            'Админ → Настройки → URL мини-приложения (или WEB_APP_URL в .env).'
        )


# Старая FSM-регистрация в боте отключена — всё в Mini App.
@router.message(Registration.display_name)
@router.message(Registration.grade)
@router.message(Registration.goal)
@router.message(Registration.city)
@router.message(Registration.city_pick)
@router.message(Registration.school)
@router.message(Registration.school_pick)
async def reg_redirect_to_miniapp(message: types.Message, state: FSMContext):
    await state.clear()
    mini_kb = miniapp_inline_keyboard()
    text = 'Регистрация перенесена в мини-приложение. Открой его и заполни профиль там.'
    if mini_kb:
        await message.answer(text, reply_markup=mini_kb)
    else:
        await message.answer(text)


@router.callback_query(F.data.startswith('citypick:'))
@router.callback_query(F.data.startswith('schoolpick:'))
async def reg_pick_redirect(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    mini_kb = miniapp_inline_keyboard()
    text = 'Регистрация в мини-приложении.'
    if mini_kb:
        await callback.message.answer(text, reply_markup=mini_kb)
    else:
        await callback.message.answer(text)


async def _start_session_flow(message: types.Message, state: FSMContext, session):
    await state.clear()
    session_task = await get_next_session_task(session)
    if not session_task:
        await message.answer('В этой сессии заданий нет. Попробуй другой режим.')
        return
    await message.answer(
        f'Сессия: {session.tasks_completed}/{session.tasks_total}',
        reply_markup=main_menu_keyboard(),
    )
    await _send_task(message, state, session_task)


@router.message(F.text.in_({'🔥 Тренировка', 'Тренировка'}))
async def start_train(message: types.Message, state: FSMContext):
    student = await _get_registered_student(message)
    if not student:
        return
    can, reason = await student_can_practice(student)
    if not can:
        await message.answer(reason)
        return
    await student.update_activity_streak()
    session = await create_train_session(student, count=20)
    await message.answer('Тренировка на 20 заданий. Можно решать подряд — без «слабой темы».')
    await _start_session_flow(message, state, session)


@router.message(F.text.in_({'📚 На сегодня', '📚 Сегодняшние задания', 'На сегодня'}))
async def start_daily_session(message: types.Message, state: FSMContext):
    student = await _get_registered_student(message)
    if not student:
        return
    can, reason = await student_can_practice(student)
    if not can:
        await message.answer(reason)
        return
    await student.update_activity_streak()
    session = await get_or_create_daily_session(student)
    session_task = await get_next_session_task(session)
    if not session_task:
        await message.answer(
            f'Дневная порция закрыта: {session.tasks_completed}/{session.tasks_total}.\n'
            f'Хочешь ещё — жми «🔥 Тренировка».'
        )
        return
    await message.answer(f'На сегодня: {session.tasks_completed}/{session.tasks_total}')
    await _send_task(message, state, session_task)


@router.message(F.text.in_({'🎯 Мои ошибки', 'Мои ошибки'}))
async def start_mistakes(message: types.Message, state: FSMContext):
    student = await _get_registered_student(message)
    if not student:
        return
    can, reason = await student_can_practice(student)
    if not can:
        await message.answer(reason)
        return
    await student.update_activity_streak()
    session = await create_mistakes_session(student, count=15)
    await message.answer('Разбираем темы, где были ошибки.')
    await _start_session_flow(message, state, session)


@router.message(F.text.in_({'🎟 Варианты', 'Варианты'}))
async def variants_menu(message: types.Message):
    student = await _get_registered_student(message)
    if not student:
        return
    from knowledge.models import ExamVariant

    total = await ExamVariant.objects.filter(is_active=True).acount()
    if total == 0:
        await message.answer(
            'Режим «полный вариант / билет» почти готов.\n\n'
            'Нужны официальные сборники РИКЗ — список в `materials/russian/SOURCES.txt`.\n'
            'Когда положишь PDF в `materials/russian/11_klass/variants/`, импортируем варианты '
            'и появится: выбрать билет → пройти → статус «пройден/не пройден».'
        )
        return
    await message.answer(f'В базе вариантов: {total}. Выбор билета подключим следующим шагом после импорта.')


@router.message(F.text.in_({'📖 По теме', '📖 Практика по теме', 'По теме'}))
async def practice_by_topic(message: types.Message, state: FSMContext):
    student = await _get_registered_student(message)
    if not student:
        return

    can, reason = await student_can_practice(student)
    if not can:
        await message.answer(reason)
        return

    topics = [
        (t.id, t.name)
        async for t in Topic.objects.filter(
            section__exam_track_id=student.exam_track_id,
            is_active=True,
        ).order_by('section__order', 'order', 'name')[:40]
    ]
    if not topics:
        await message.answer('Темы ещё не загружены.')
        return

    await state.set_state(TopicPractice.choose_topic)
    await message.answer('Выбери тему:', reply_markup=topics_keyboard(topics))


@router.callback_query(F.data.startswith('topic:'))
async def topic_chosen(callback: types.CallbackQuery, state: FSMContext):
    student = await Student.objects.filter(tg_id=callback.from_user.id, registration_completed=True).afirst()
    if not student:
        await callback.answer('Сначала /start', show_alert=True)
        return

    topic_id = int(callback.data.split(':')[1])
    topic = await Topic.objects.aget(id=topic_id)
    session = await create_topic_practice_session(student, topic, count=5)
    session_task = await get_next_session_task(session)
    await state.clear()
    if not session_task:
        await callback.message.answer('По этой теме пока нет доступных заданий.')
        await callback.answer()
        return

    await callback.message.answer(f'Практика: {topic.name}')
    await _send_task(callback.message, state, session_task)
    await callback.answer()


@router.callback_query(F.data == 'next_task')
async def next_task_callback(callback: types.CallbackQuery, state: FSMContext):
    from learning.models import DailySession

    student = await Student.objects.filter(tg_id=callback.from_user.id, registration_completed=True).afirst()
    if not student:
        await callback.answer('Сначала /start')
        return

    can, reason = await student_can_practice(student)
    if not can:
        await callback.message.answer(reason)
        await callback.answer()
        return

    session = await (
        DailySession.objects.filter(student=student, status=DailySession.Status.IN_PROGRESS)
        .order_by('-created_at')
        .afirst()
    )
    if not session:
        session = await get_or_create_daily_session(student)

    session_task = await get_next_session_task(session)
    if not session_task:
        await callback.message.answer(
            '🎉 Сессия завершена.\nМожно снова: «🔥 Тренировка» или «🎯 Мои ошибки».'
        )
        await callback.answer()
        return

    await _send_task(callback.message, state, session_task)
    await callback.answer()


@router.callback_query(F.data.startswith('toggle:'))
async def toggle_option(callback: types.CallbackQuery, state: FSMContext):
    _, session_task_id, opt_num = callback.data.split(':')
    session_task_id = int(session_task_id)
    opt_num = int(opt_num)

    data = await state.get_data()
    selected = set(data.get('selected') or [])
    if data.get('session_task_id') != session_task_id:
        selected = set()
        await state.set_state(DailyPractice.multi_select)
        await state.update_data(session_task_id=session_task_id)

    if opt_num in selected:
        selected.remove(opt_num)
    else:
        selected.add(opt_num)
    await state.update_data(selected=sorted(selected), session_task_id=session_task_id)

    from learning.models import SessionTask

    session_task = await SessionTask.objects.select_related('task').aget(id=session_task_id)
    options = [o async for o in TaskOption.objects.filter(task=session_task.task).order_by('order')]
    kb = multi_choice_keyboard(
        session_task_id,
        [(o.order or idx, o.text, (o.order or idx) in selected) for idx, o in enumerate(options, 1)],
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith('submit:'))
async def submit_multi_choice(callback: types.CallbackQuery, state: FSMContext):
    session_task_id = int(callback.data.split(':')[1])
    student = await Student.objects.filter(tg_id=callback.from_user.id).afirst()
    if not student:
        await callback.answer('Ошибка')
        return

    data = await state.get_data()
    selected = data.get('selected') or []
    if not selected:
        await callback.answer('Выбери хотя бы один вариант', show_alert=True)
        return

    from learning.models import SessionTask

    session_task = await SessionTask.objects.select_related('task', 'session', 'task__topic').aget(
        id=session_task_id
    )
    if session_task.is_answered:
        await callback.answer('Уже отвечено')
        return

    answer_text = ', '.join(str(x) for x in sorted(selected))
    spent = _elapsed_seconds(data)
    attempt = await submit_answer(
        student, session_task, answer_text, time_spent_seconds=spent
    )
    await state.clear()
    await _reply_after_attempt(callback.message, student, session_task, attempt)
    await callback.answer()


@router.callback_query(F.data.startswith('answer:'))
async def process_single_choice(callback: types.CallbackQuery, state: FSMContext):
    """Один вариант (single_choice) — сразу отправляем ответ-номер."""
    _, session_task_id, option_id = callback.data.split(':')
    student = await Student.objects.filter(tg_id=callback.from_user.id).afirst()
    if not student:
        await callback.answer('Ошибка')
        return

    from learning.models import SessionTask

    data = await state.get_data()
    session_task = await SessionTask.objects.select_related('task', 'session').aget(id=int(session_task_id))
    option = await TaskOption.objects.aget(id=int(option_id))
    # для проверки по ключу РИКЗ удобнее номер варианта
    answer = str(option.order or option.id)
    spent = _elapsed_seconds(data)
    attempt = await submit_answer(
        student, session_task, answer, time_spent_seconds=spent
    )
    await state.clear()
    await _reply_after_attempt(callback.message, student, session_task, attempt)
    await callback.answer()


@router.message(DailyPractice.waiting_answer)
async def process_text_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    session_task_id = data.get('session_task_id')
    if not session_task_id:
        await state.clear()
        return

    from learning.models import SessionTask

    student = await Student.objects.filter(tg_id=message.from_user.id).afirst()
    session_task = await SessionTask.objects.select_related('task', 'session').aget(id=session_task_id)
    spent = _elapsed_seconds(data)
    attempt = await submit_answer(
        student, session_task, message.text, time_spent_seconds=spent
    )
    await state.clear()
    await _reply_after_attempt(message, student, session_task, attempt)


@router.callback_query(F.data.startswith('ai:'))
async def ai_explain_callback(callback: types.CallbackQuery):
    student = await Student.objects.filter(tg_id=callback.from_user.id).afirst()
    can, use_llm, reason = await student_can_request_ai(student)
    if not can:
        await callback.answer(reason, show_alert=True)
        return

    session_task_id = int(callback.data.split(':')[1])
    from learning.models import TaskAttempt

    attempt = await (
        TaskAttempt.objects.filter(session_task_id=session_task_id, student=student)
        .select_related('task', 'task__topic')
        .order_by('-created_at')
        .afirst()
    )
    if not attempt:
        await callback.answer('Сначала ответь на задание.')
        return

    await callback.message.answer(
        '⏳ Готовлю разбор...' if use_llm else '⏳ Смотрю эталон...'
    )
    explanation = await explain_mistake(attempt, use_llm=use_llm)
    # Telegram limit ~4096
    if len(explanation) > 3500:
        explanation = explanation[:3500] + '…'
    await callback.message.answer(f'📖 Разбор:\n\n{explanation}')
    await callback.answer()


@router.message(F.text.in_({'📊 Статистика', '📊 Моя статистика', 'Статистика'}))
async def show_stats(message: types.Message):
    student = await _get_registered_student(message)
    if not student:
        return

    weak = await get_weak_topics(student, limit=5)
    if weak:
        lines = ['📊 Твои слабые темы:']
        for mastery in weak:
            lines.append(
                f'• {mastery.topic.name} — {mastery.mastery_score:.0%} '
                f'({mastery.correct_count}✓ / {mastery.wrong_count}✗)'
            )
    else:
        lines = ['📊 Пока мало данных. Реши несколько заданий — покажу слабые места.']

    sessions = await get_recent_sessions(student, limit=5)
    done = [s for s in sessions if s.max_primary > 0]
    if done:
        best = max(done, key=lambda s: (s.test_score or 0, s.primary_score))
        lines.append(
            f'\nЛучшая недавняя сессия: первичный {best.primary_score}/{best.max_primary}'
        )
        if best.test_score is not None:
            lines.append(f'Тестовый (шкала РИКЗ): ≈{best.test_score}')

    lines.append(
        f'\nXP: {student.xp} | Серия: {student.streak_days} дн. | '
        f'Сегодня решено: {student.daily_tasks_completed}'
    )
    await message.answer('\n'.join(lines))


@router.message(F.text.in_({'📜 История', 'История'}))
async def show_history(message: types.Message):
    student = await _get_registered_student(message)
    if not student:
        return

    kind_labels = {
        'daily': 'На сегодня',
        'train': 'Тренировка',
        'variant': 'Вариант',
        'mistakes': 'Ошибки',
    }
    sessions = await get_recent_sessions(student, limit=8)
    attempts = await get_recent_attempts(student, limit=12)

    if not sessions and not attempts:
        await message.answer('История пуста — реши пару заданий.')
        return

    lines = ['📜 Последние сессии:']
    if sessions:
        for s in sessions:
            label = kind_labels.get(s.kind, s.kind)
            status = '✓' if s.status == 'completed' else '…'
            score = ''
            if s.max_primary:
                score = f' · {s.primary_score}/{s.max_primary} перв.'
                if s.test_score is not None:
                    score += f' → ≈{s.test_score} тест.'
            lines.append(
                f'{status} {s.session_date} · {label} · '
                f'{s.tasks_completed}/{s.tasks_total}{score}'
            )
    else:
        lines.append('пока нет')

    lines.append('\nПоследние ответы:')
    if attempts:
        for a in attempts:
            if a.is_correct:
                mark = '✅'
            elif a.points_earned > 0:
                mark = '🟡'
            else:
                mark = '❌'
            topic = a.task.topic.name if a.task_id else '—'
            when = timezone.localtime(a.created_at).strftime('%d.%m %H:%M')
            lines.append(
                f'{mark} {when} · {topic[:40]} · {a.points_earned}/{a.max_points}'
            )
    else:
        lines.append('пока нет')

    text = '\n'.join(lines)
    if len(text) > 3800:
        text = text[:3800] + '…'
    await message.answer(text)

@router.message(F.text == '🏆 Рейтинг')
async def show_rating(message: types.Message):
    student = await _get_registered_student(message)
    if not student:
        return
    await message.answer('Выбери рейтинг:', reply_markup=rating_scope_keyboard())


@router.callback_query(F.data.startswith('rating:'))
async def rating_callback(callback: types.CallbackQuery):
    scope = callback.data.split(':')[1]
    student = await (
        Student.objects.select_related('city', 'school')
        .filter(tg_id=callback.from_user.id, registration_completed=True)
        .afirst()
    )
    if not student:
        await callback.answer('Сначала /start')
        return

    entries, title = await get_leaderboard(scope=scope, student=student, limit=10)
    if not entries:
        await callback.message.answer(f'{title}\nПока пусто.')
        await callback.answer()
        return

    lines = [f'🏆 {title}']
    for idx, row in enumerate(entries, 1):
        lines.append(f'{idx}. {row["display_name"]} — {row["xp"]} XP')
    await callback.message.answer('\n'.join(lines))
    await callback.answer()


@router.message(F.text == '⚙️ Профиль')
async def show_profile(message: types.Message):
    student = await (
        Student.objects.select_related('subject', 'exam_track', 'city', 'school')
        .filter(tg_id=message.from_user.id, registration_completed=True)
        .afirst()
    )
    if not student:
        await message.answer('Сначала пройди регистрацию: /start')
        return

    settings = await AppSettings.aget_settings()
    pro = 'Pro ✅' if student.has_active_pro else 'Free'
    free_info = (
        f'Free: до {settings.free_daily_tasks_limit} заданий/день'
        if settings.free_mode_enabled
        else 'Free-режим выключен админом'
    )
    city = student.city.name if student.city_id else '—'
    school = student.school.name if student.school_id else '—'
    await message.answer(
        f'👤 {student.display_name}\n'
        f'Класс: {student.grade}\n'
        f'Предмет: {student.subject.name}\n'
        f'Программа: {student.exam_track.name}\n'
        f'Город: {city}\n'
        f'Школа: {school}\n'
        f'Тариф: {pro}\n'
        f'{free_info}\n'
        f'XP: {student.xp} | Серия: {student.streak_days} дн.'
    )


@router.message(F.text.in_({'👨‍👩‍👧 Родителям', 'Родителям'}))
async def student_parent_invite(message: types.Message):
    student = await _get_registered_student(message)
    if not student:
        return
    invite = await get_active_invite(student)
    if not invite:
        invite = await issue_parent_invite(student)
    linked = await ParentChildLink.objects.filter(student=student).acount()
    await message.answer(
        '👨‍👩‍👧 Чтобы родитель видел твой прогресс:\n\n'
        f'1) Отправь ему код: `{invite.code}`\n'
        '2) Родитель вводит код во вкладке «Семья» в мини-приложении '
        'или в боте → «Я родитель» → «Привязать по коду»\n'
        f'3) Код действует до {timezone.localtime(invite.expires_at).strftime("%d.%m.%Y")}\n\n'
        f'Сейчас привязано родителей: {linked}\n'
        'Новый код: напиши «новый код родителя» или обнови во вкладке «Семья».',
        parse_mode='Markdown',
    )


@router.message(F.text.in_({'новый код родителя', 'Новый код родителя'}))
async def student_parent_invite_refresh(message: types.Message):
    student = await _get_registered_student(message)
    if not student:
        return
    invite = await issue_parent_invite(student)
    await message.answer(
        f'Новый код: `{invite.code}`\n'
        f'Действует до {timezone.localtime(invite.expires_at).strftime("%d.%m.%Y")}',
        parse_mode='Markdown',
    )


@router.message(F.text.in_({'👨‍👩‍👧 Я родитель', 'Я родитель'}))
async def parent_mode(message: types.Message, state: FSMContext):
    await state.clear()
    parent = await get_or_create_parent(
        message.from_user.id,
        username=message.from_user.username or '',
        display_name=(message.from_user.full_name or '')[:100],
    )
    children = await list_children(parent)
    if children:
        names = ', '.join(c.display_name for c in children)
        await message.answer(
            f'Режим родителя. Привязаны: {names}\n'
            'Можно смотреть отчёт или привязать ещё одного ребёнка.',
            reply_markup=parent_menu_keyboard(),
        )
    else:
        await message.answer(
            'Режим родителя.\n'
            'Попроси у ребёнка код (бот → «Родителям» или мини-приложение → «Семья») '
            'и введи его здесь («🔗 Привязать по коду») или во вкладке «Семья».',
            reply_markup=parent_menu_keyboard(),
        )


@router.message(F.text == '⬅️ В обычное меню')
async def parent_back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer('Обычное меню:', reply_markup=main_menu_keyboard())


@router.message(F.text == '🔗 Привязать по коду')
async def parent_ask_code(message: types.Message, state: FSMContext):
    await get_or_create_parent(
        message.from_user.id,
        username=message.from_user.username or '',
        display_name=(message.from_user.full_name or '')[:100],
    )
    await state.set_state(ParentFlow.enter_code)
    await message.answer(
        'Введи код ребёнка (6 символов):',
        reply_markup=cancel_keyboard(),
    )


@router.message(ParentFlow.enter_code)
async def parent_enter_code(message: types.Message, state: FSMContext):
    if _is_cancel(message.text):
        await state.clear()
        await message.answer('Отменено.', reply_markup=parent_menu_keyboard())
        return
    parent = await get_or_create_parent(message.from_user.id)
    _, status = await link_parent_by_code(parent, message.text or '')
    await state.clear()
    await message.answer(status, reply_markup=parent_menu_keyboard())


@router.message(F.text == '📊 Отчёт по ребёнку')
async def parent_report_menu(message: types.Message):
    parent = await get_or_create_parent(message.from_user.id)
    children = await list_children(parent)
    if not children:
        await message.answer(
            'Сначала привяжи ребёнка кодом.',
            reply_markup=parent_menu_keyboard(),
        )
        return
    if len(children) == 1:
        report = await build_parent_report(children[0])
        await message.answer(report)
        return
    await message.answer(
        'Выбери ребёнка:',
        reply_markup=children_pick_keyboard([(c.id, c.display_name) for c in children]),
    )


@router.callback_query(F.data.startswith('parent_child:'))
async def parent_report_child(callback: types.CallbackQuery):
    student_id = int(callback.data.split(':')[1])
    parent = await Parent.objects.filter(tg_id=callback.from_user.id).afirst()
    if not parent:
        await callback.answer('Сначала «Я родитель»', show_alert=True)
        return
    linked = await ParentChildLink.objects.filter(
        parent=parent, student_id=student_id
    ).aexists()
    if not linked:
        await callback.answer('Нет доступа', show_alert=True)
        return
    student = await Student.objects.select_related('city', 'school').aget(id=student_id)
    report = await build_parent_report(student)
    await callback.message.answer(report)
    await callback.answer()


@router.message(Command('help'))
async def cmd_help(message: types.Message):
    await message.answer(
        'Команды:\n'
        '/start — регистрация\n'
        '/help — помощь\n\n'
        '🔥 Тренировка — длинная сессия (погружение)\n'
        '📚 На сегодня — дневная порция\n'
        '🎯 Мои ошибки — темы, где косячил\n'
        '🎟 Варианты — полные билеты из сборников (после импорта PDF)\n'
        '📖 По теме — выбрать тему\n'
        '📊 Статистика / 📜 История / 🏆 Рейтинг\n'
        '👨‍👩‍👧 Родителям — код для мамы/папы\n'
        '👨‍👩‍👧 Я родитель — привязка и отчёт по ребёнку\n'
        '📱 Мини-приложение — кнопка в меню\n\n'
        'Баллы: первичные как на ЦТ + ориентир тестового по шкале РИКЗ 2025.\n'
        'ИИ-разбор ошибок: тариф «Разбор с ИИ» + ключ DeepSeek.'
    )


def _elapsed_seconds(data: dict) -> int:
    started = data.get('task_started_at')
    if not started:
        return 0
    try:
        return max(0, int(timezone.now().timestamp() - float(started)))
    except (TypeError, ValueError):
        return 0


async def _get_registered_student(message: types.Message) -> Student | None:
    student = await Student.objects.filter(
        tg_id=message.from_user.id, registration_completed=True
    ).afirst()
    if not student:
        mini_kb = miniapp_inline_keyboard()
        text = 'Сначала регистрация в мини-приложении (кнопка ниже или /start).'
        if mini_kb:
            await message.answer(text, reply_markup=mini_kb)
        else:
            await message.answer(text)
        return None
    return student


async def _send_task(message: types.Message, state: FSMContext, session_task):
    from learning.models import SessionTask as ST

    task = await Task.objects.select_related('topic').aget(pk=session_task.task_id)
    purpose_part = ''
    if session_task.purpose == ST.Purpose.WEAK_TOPIC:
        purpose_part = ' · нужно подтянуть'
    elif session_task.purpose == ST.Purpose.REVIEW:
        purpose_part = ' · повторение'

    header = (
        f'Задание {session_task.order + 1}{purpose_part}\n'
        f'Тема: {task.topic.name}\n\n'
        f'{task.question}'
    )

    if task.answer_format == Task.AnswerFormat.MULTIPLE_CHOICE:
        options = [o async for o in TaskOption.objects.filter(task=task).order_by('order')]
        if options:
            await state.set_state(DailyPractice.multi_select)
            await state.update_data(
                session_task_id=session_task.id,
                selected=[],
                task_started_at=timezone.now().timestamp(),
            )
            kb = multi_choice_keyboard(
                session_task.id,
                [(o.order or idx, o.text, False) for idx, o in enumerate(options, 1)],
            )
            await message.answer(
                header + '\n\n☑️ Можно выбрать несколько вариантов, затем «Ответить».',
                reply_markup=kb,
            )
            return

    if task.answer_format == Task.AnswerFormat.SINGLE_CHOICE:
        options = [o async for o in TaskOption.objects.filter(task=task).order_by('order')]
        if options:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            rows = [
                [
                    InlineKeyboardButton(
                        text=opt.text[:60],
                        callback_data=f'answer:{session_task.id}:{opt.id}',
                    )
                ]
                for opt in options
            ]
            await state.update_data(
                session_task_id=session_task.id,
                task_started_at=timezone.now().timestamp(),
            )
            await message.answer(header, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
            return

    await state.set_state(DailyPractice.waiting_answer)
    await state.update_data(
        session_task_id=session_task.id,
        task_started_at=timezone.now().timestamp(),
    )
    await message.answer(
        header + '\n\n✏️ Напиши ответ текстом '
        '(например: `1, 3, 5` или `А5Б3В4Г1` или слово):',
        parse_mode=None,
    )


async def _reply_after_attempt(message, student, session_task, attempt):
    can_ai, _, _ = await student_can_request_ai(student)
    from knowledge.models import TaskSolution
    from learning.models import DailySession

    pts = f'{attempt.points_earned}/{attempt.max_points} перв.'
    if attempt.is_correct:
        text = f'✅ Верно! ({pts})'
        kb = after_answer_keyboard(session_task.id, can_ai=False)
    elif attempt.points_earned > 0:
        correct = ''
        try:
            solution = await TaskSolution.objects.aget(task_id=session_task.task_id)
            correct = f'\nЭталон: {solution.correct_answer}'
        except TaskSolution.DoesNotExist:
            pass
        text = f'🟡 Частично верно ({pts}).{correct}'
        kb = after_answer_keyboard(session_task.id, can_ai=can_ai)
    else:
        correct = ''
        try:
            solution = await TaskSolution.objects.aget(task_id=session_task.task_id)
            correct = f'\n\nПравильный ответ: {solution.correct_answer}'
        except TaskSolution.DoesNotExist:
            pass
        text = f'❌ Неверно (0/{attempt.max_points}).{correct}'
        kb = after_answer_keyboard(session_task.id, can_ai=can_ai)

    session = await DailySession.objects.aget(pk=session_task.session_id)
    if session.tasks_total:
        text += (
            f'\n\nСессия: {session.tasks_completed}/{session.tasks_total} · '
            f'первичный {session.primary_score}/{session.max_primary}'
        )
        if session.test_score is not None:
            text += f' · тестовый ≈{session.test_score}'

    await message.answer(text, reply_markup=kb)
