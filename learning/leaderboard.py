"""Рейтинги, недельные и месячные лиги с автоматическим сбросом и сохранением истории."""

import calendar
from datetime import timedelta
from django.db.models import F
from django.utils import timezone

from learning.models import LeagueEntry, WeeklyLeague
from students.models import Student


def week_bounds(today=None):
    today = today or timezone.localdate()
    week_start = today - timedelta(days=today.weekday())  # понедельник
    week_end = week_start + timedelta(days=6)  # воскресенье
    return week_start, week_end


def month_bounds(today=None):
    today = today or timezone.localdate()
    month_start = today.replace(day=1)  # 1-е число месяца
    _, last_day = calendar.monthrange(today.year, today.month)
    month_end = today.replace(day=last_day)
    return month_start, month_end


async def get_or_create_active_league(period_type: str = 'week') -> WeeklyLeague:
    """
    Возвращает текущую активную лигу за неделю или за месяц.
    История предыдущих периодов сохраняется в БД навсегда.
    """
    if period_type == WeeklyLeague.PeriodType.MONTH:
        start_d, end_d = month_bounds()
        default_title = f'Турнир месяца ({start_d.strftime("%B %Y")})'
    else:
        period_type = WeeklyLeague.PeriodType.WEEK
        start_d, end_d = week_bounds()
        default_title = f'Турнир недели ({start_d.strftime("%d.%m")} — {end_d.strftime("%d.%m")})'

    league, created = await WeeklyLeague.objects.aget_or_create(
        period_type=period_type,
        week_start=start_d,
        defaults={
            'week_end': end_d,
            'title': default_title,
            'is_active': True,
            'prize_first_place': '',
            'prize_second_place': '',
            'prize_third_place': '',
            'prizes_text': '',
        },
    )
    return league


async def record_student_activity(student: Student, xp: int = 0, test_score: int = 0, primary_score: int = 0) -> None:
    """
    Записывает результаты ученика и в недельный, и в месячный турниры.
    """
    for period in (WeeklyLeague.PeriodType.WEEK, WeeklyLeague.PeriodType.MONTH):
        league = await get_or_create_active_league(period)
        entry, created = await LeagueEntry.objects.aget_or_create(
            league=league,
            student=student,
            defaults={
                'weekly_xp': max(0, xp),
                'test_score': max(0, test_score),
                'primary_score': max(0, primary_score),
            },
        )
        if not created:
            updates = {}
            if xp > 0:
                entry.weekly_xp = F('weekly_xp') + xp
                updates['weekly_xp'] = entry.weekly_xp
            if primary_score > 0:
                entry.primary_score = F('primary_score') + primary_score
                updates['primary_score'] = entry.primary_score
            if test_score > entry.test_score:
                entry.test_score = test_score
                updates['test_score'] = test_score

            if updates:
                await LeagueEntry.objects.filter(pk=entry.pk).aupdate(**updates)


async def add_weekly_xp(student: Student, xp: int) -> None:
    """Обратная совместимость для начисления XP."""
    await record_student_activity(student, xp=xp)


async def get_leaderboard(scope: str = 'all', student: Student | None = None, limit: int = 10) -> tuple[list[dict], str]:
    """
    Возвращает топ лиги по фильтру (scope: 'all', 'school', 'city').
    Возвращает кортеж (entries, title).
    """
    league = await get_or_create_active_league(WeeklyLeague.PeriodType.WEEK)
    qs = LeagueEntry.objects.filter(league=league).select_related('student', 'student__city', 'student__school')

    if scope == 'school' and student and getattr(student, 'school_id', None):
        qs = qs.filter(student__school_id=student.school_id)
        school_name = student.school.name if student.school else 'Школа'
        title = f'Рейтинг школы ({school_name})'
    elif scope == 'city' and student and getattr(student, 'city_id', None):
        qs = qs.filter(student__city_id=student.city_id)
        city_name = student.city.name if student.city else 'Город'
        title = f'Рейтинг города ({city_name})'
    else:
        title = 'Общий турнирный рейтинг'

    qs = qs.order_by('-weekly_xp', '-primary_score')[:limit]

    entries = []
    async for entry in qs:
        st = entry.student
        name = (st.first_name or 'Ученик') if st else 'Ученик'
        entries.append({
            'student_id': st.id if st else None,
            'display_name': name,
            'xp': entry.weekly_xp,
            'test_score': entry.test_score,
            'primary_score': entry.primary_score,
        })
    return entries, title


get_or_create_current_league = get_or_create_active_league
