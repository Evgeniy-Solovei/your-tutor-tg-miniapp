"""Привязка родителей и текстовые отчёты в Telegram."""

from __future__ import annotations

import secrets
import string
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.db.models import Count, Q, Sum
from django.utils import timezone

from learning.leaderboard import get_or_create_current_league, week_bounds
from learning.models import DailySession, LeagueEntry, TaskAttempt, TopicMastery
from students.models import Parent, ParentChildLink, ParentInvite, Student


def _new_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # без похожих символов
    alphabet = alphabet.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_or_create_parent(tg_id: int, *, username: str = '', display_name: str = '') -> Parent:
    parent, created = await Parent.objects.aget_or_create(
        tg_id=tg_id,
        defaults={
            'username': username or '',
            'display_name': display_name or '',
        },
    )
    if not created:
        fields = []
        if username and parent.username != username:
            parent.username = username
            fields.append('username')
        if display_name and not parent.display_name:
            parent.display_name = display_name
            fields.append('display_name')
        if fields:
            await parent.asave(update_fields=fields)
    return parent


async def issue_parent_invite(student: Student, *, days: int = 14) -> ParentInvite:
    """Выдать/обновить активный код для ученика."""
    await ParentInvite.objects.filter(student=student, is_active=True).aupdate(is_active=False)
    for _ in range(12):
        code = _new_code()
        if not await ParentInvite.objects.filter(code=code).aexists():
            return await ParentInvite.objects.acreate(
                student=student,
                code=code,
                is_active=True,
                expires_at=timezone.now() + timedelta(days=days),
            )
    raise RuntimeError('Не удалось сгенерировать код')


async def get_active_invite(student: Student) -> ParentInvite | None:
    now = timezone.now()
    invite = await (
        ParentInvite.objects.filter(student=student, is_active=True, expires_at__gt=now)
        .order_by('-created_at')
        .afirst()
    )
    return invite


async def link_parent_by_code(parent: Parent, code: str) -> tuple[ParentChildLink | None, str]:
    code = (code or '').strip().upper()
    if len(code) < 4:
        return None, 'Код слишком короткий. Попроси ребёнка код из «Семья» или бота → «Родителям».'

    invite = await (
        ParentInvite.objects.select_related('student')
        .filter(code=code, is_active=True)
        .afirst()
    )
    if not invite:
        return None, 'Код не найден или уже не действует.'
    if invite.expires_at <= timezone.now():
        invite.is_active = False
        await invite.asave(update_fields=['is_active'])
        return None, 'Срок кода истёк. Пусть ребёнок создаст новый в «Родителям».'

    link, created = await ParentChildLink.objects.aget_or_create(
        parent=parent,
        student_id=invite.student_id,
    )
    if created:
        return link, f'Готово! Привязан(а): {invite.student.display_name}.'
    return link, f'Уже привязан(а): {invite.student.display_name}.'


async def list_children(parent: Parent) -> list[Student]:
    return [
        link.student
        async for link in ParentChildLink.objects.filter(parent=parent)
        .select_related('student', 'student__city', 'student__school')
        .order_by('student__display_name')
    ]


def _format_minutes(seconds: int) -> str:
    minutes = max(0, seconds) // 60
    sec = max(0, seconds) % 60
    if minutes == 0:
        return f'{sec} сек'
    if sec == 0:
        return f'{minutes} мин'
    return f'{minutes} мин {sec} сек'


async def student_weekly_rank(student: Student, scope: str) -> str:
    """Место ребёнка в недельной лиге по городу/школе (по weekly XP)."""
    league = await get_or_create_current_league()
    qs = LeagueEntry.objects.filter(league=league).select_related('student')
    if scope == 'city':
        if not student.city_id:
            return 'город не указан'
        qs = qs.filter(student__city_id=student.city_id)
        label = getattr(student, 'city', None).name if getattr(student, 'city', None) else 'город'
    elif scope == 'school':
        if not student.school_id:
            return 'школа не указана'
        qs = qs.filter(student__school_id=student.school_id)
        label = getattr(student, 'school', None).name if getattr(student, 'school', None) else 'школа'
    else:
        label = 'страна'

    my = await qs.filter(student=student).afirst()
    if not my:
        return f'{label}: пока нет активности на этой неделе'

    better = await qs.filter(weekly_xp__gt=my.weekly_xp).acount()
    total = await qs.acount()
    place = better + 1
    return f'{label}: {place}-е место из {total} (нед. XP {my.weekly_xp})'


def resolve_report_period(
    period: str = 'week',
    *,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """Вернуть (start_date, end_date, label). period: week | month | custom."""
    today = timezone.localdate()
    period = (period or 'week').strip().lower()

    if period == 'month':
        start = today.replace(day=1)
        return start, today, f'Месяц: {start.strftime("%d.%m")}–{today.strftime("%d.%m")}'

    if period == 'custom':
        from datetime import date as date_cls

        try:
            start = date_cls.fromisoformat((date_from or '').strip()[:10])
            end = date_cls.fromisoformat((date_to or '').strip()[:10])
        except ValueError as exc:
            raise ValueError('Укажи даты в формате ГГГГ-ММ-ДД') from exc
        if end < start:
            raise ValueError('Дата «по» не может быть раньше «с»')
        if (end - start).days > 92:
            raise ValueError('Период не больше 3 месяцев')
        if end > today:
            end = today
        return start, end, f'Период: {start.strftime("%d.%m")}–{end.strftime("%d.%m")}'

    # week (default)
    start, end = week_bounds(today)
    if end > today:
        end = today
    return start, end, f'Неделя: {start.strftime("%d.%m")}–{end.strftime("%d.%m")}'


async def build_parent_report(
    student: Student,
    *,
    period: str = 'week',
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """Текст отчёта для родителя в Telegram за выбранный период."""
    start, end, period_label = resolve_report_period(
        period, date_from=date_from, date_to=date_to
    )
    student = await Student.objects.select_related('city', 'school').aget(pk=student.pk)

    @sync_to_async
    def attempt_stats():
        return TaskAttempt.objects.filter(
            student=student,
            created_at__date__gte=start,
            created_at__date__lte=end,
        ).aggregate(
            total=Count('id'),
            correct=Count('id', filter=Q(is_correct=True)),
            seconds=Sum('time_spent_seconds'),
        )

    @sync_to_async
    def time_by_day():
        rows = (
            TaskAttempt.objects.filter(
                student=student,
                created_at__date__gte=start,
                created_at__date__lte=end,
            )
            .values('created_at__date')
            .annotate(
                seconds=Sum('time_spent_seconds'),
                tasks=Count('id'),
            )
            .order_by('created_at__date')
        )
        return list(rows)

    @sync_to_async
    def period_sessions():
        return list(
            DailySession.objects.filter(
                student=student,
                session_date__gte=start,
                session_date__lte=end,
            )
            .order_by('-session_date')
            .values(
                'session_date',
                'tasks_completed',
                'tasks_total',
                'primary_score',
                'max_primary',
                'test_score',
                'kind',
            )[:21]
        )

    stats = await attempt_stats()
    by_day = await time_by_day()
    sessions = await period_sessions()

    weak = [
        m
        async for m in TopicMastery.objects.filter(student=student, wrong_count__gt=0)
        .select_related('topic')
        .order_by('mastery_score')[:5]
    ]

    total = stats.get('total') or 0
    correct = stats.get('correct') or 0
    seconds = stats.get('seconds') or 0
    acc = f'{round(100 * correct / total)}%' if total else '—'

    lines = [
        f'👨‍👩‍👧 Отчёт: {student.display_name}',
        period_label,
        '',
        '📚 Прогресс',
        f'• заданий за период: {total} (верно {correct}, точность {acc})',
        f'• серийность сейчас: {student.streak_days} дн.',
        f'• суммарное время (замер в боте): {_format_minutes(seconds) if seconds else "пока не замерялось / ~0"}',
        '',
        '⏱ Время по дням',
    ]
    if by_day:
        # для длинных периодов — не больше 21 строки
        shown = by_day[-21:]
        for row in shown:
            d = row['created_at__date']
            sec = row['seconds'] or 0
            tasks = row['tasks'] or 0
            time_part = _format_minutes(sec) if sec else 'время не записано'
            lines.append(f'• {d.strftime("%d.%m")}: {tasks} зад. · {time_part}')
        if len(by_day) > 21:
            lines.append(f'• … и ещё {len(by_day) - 21} дн.')
    else:
        lines.append('• за этот период активности ещё не было')

    lines.append('')
    lines.append('🎯 Что подтянуть')
    if weak:
        for m in weak:
            lines.append(
                f'• {m.topic.name} — {m.mastery_score:.0%} '
                f'({m.correct_count}✓ / {m.wrong_count}✗)'
            )
    else:
        lines.append('• пока мало ошибок — или мало практики')

    # Недельный рейтинг лиги осмыслен только для текущей недели
    if (period or 'week').strip().lower() == 'week':
        city_rank = await student_weekly_rank(student, 'city')
        school_rank = await student_weekly_rank(student, 'school')
        lines += [
            '',
            '🏆 Рейтинг за неделю',
            f'• {city_rank}',
            f'• {school_rank}',
        ]

    if sessions:
        lines += ['', '📅 Сессии']
        for s in sessions[:10]:
            score = ''
            if s['max_primary']:
                score = f' · {s["primary_score"]}/{s["max_primary"]}'
                if s['test_score'] is not None:
                    score += f' → ≈{s["test_score"]}'
            lines.append(
                f'• {s["session_date"].strftime("%d.%m")}: '
                f'{s["tasks_completed"]}/{s["tasks_total"]}{score}'
            )

    lines += [
        '',
        'Запросить снова можно в мини-приложении → «Семья» или в боте.',
    ]
    text = '\n'.join(lines)
    if len(text) > 3900:
        text = text[:3900] + '…'
    return text


async def parent_has_child(parent: Parent, student_id: int) -> bool:
    return await ParentChildLink.objects.filter(parent=parent, student_id=student_id).aexists()
