"""Аналитический дашборд для админки (Unfold Admin)."""

from datetime import datetime, time, timedelta

from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from students.models import PaymentOrder, Student, UserSessionLog


def _datetime_range(start_date, end_date):
    """Полуоткрытый диапазон использует индекс timestamp без DATE(column)."""
    start = timezone.make_aware(datetime.combine(start_date, time.min))
    end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
    return start, end


def admin_analytics_view(request):
    """Метрики админки за три агрегирующих SQL-запроса вместо десятков N+1."""
    today = timezone.localdate()
    week_curr_start = today - timedelta(days=6)
    week_prev_start = today - timedelta(days=13)
    week_prev_end = today - timedelta(days=7)
    month_curr_start = today - timedelta(days=29)
    month_prev_start = today - timedelta(days=59)
    month_prev_end = today - timedelta(days=30)

    student_aggregates = {
        'total_students': Count('id'),
        'pro_students': Count('id', filter=Q(is_pro=True)),
        'wau_curr': Count('id', filter=Q(last_activity_date__gte=week_curr_start)),
        'wau_prev': Count('id', filter=Q(last_activity_date__range=(week_prev_start, week_prev_end))),
        'mau_curr': Count('id', filter=Q(last_activity_date__gte=month_curr_start)),
        'mau_prev': Count('id', filter=Q(last_activity_date__range=(month_prev_start, month_prev_end))),
    }
    session_aggregates = {
        'week_curr': Sum('duration_seconds', filter=Q(date__gte=week_curr_start)),
        'week_prev': Sum('duration_seconds', filter=Q(date__range=(week_prev_start, week_prev_end))),
        'month_curr': Sum('duration_seconds', filter=Q(date__gte=month_curr_start)),
        'month_prev': Sum('duration_seconds', filter=Q(date__range=(month_prev_start, month_prev_end))),
    }
    paid = Q(status=PaymentOrder.Status.PAID)
    payment_aggregates = {
        'total_revenue': Sum('amount_byn', filter=paid),
    }

    for key, start_date, end_date in (
        ('new_week_curr', week_curr_start, today),
        ('new_week_prev', week_prev_start, week_prev_end),
        ('new_month_curr', month_curr_start, today),
        ('new_month_prev', month_prev_start, month_prev_end),
    ):
        start_dt, end_dt = _datetime_range(start_date, end_date)
        student_aggregates[key] = Count('id', filter=Q(created_at__gte=start_dt, created_at__lt=end_dt))

    for prefix, start_date, end_date in (
        ('week_curr', week_curr_start, today),
        ('week_prev', week_prev_start, week_prev_end),
        ('month_curr', month_curr_start, today),
        ('month_prev', month_prev_start, month_prev_end),
    ):
        start_dt, end_dt = _datetime_range(start_date, end_date)
        payment_filter = paid & Q(paid_at__gte=start_dt, paid_at__lt=end_dt)
        payment_aggregates[f'{prefix}_revenue'] = Sum('amount_byn', filter=payment_filter)
        payment_aggregates[f'{prefix}_count'] = Count('id', filter=payment_filter)

    # Девять недель нужны, чтобы посчитать рост для самой старой из 8 строк.
    weeks = []
    for i in range(9):
        start_date = today - timedelta(days=(i * 7) + 6)
        end_date = today - timedelta(days=i * 7)
        weeks.append((start_date, end_date))
        start_dt, end_dt = _datetime_range(start_date, end_date)
        student_aggregates[f'w{i}_active'] = Count(
            'id', filter=Q(last_activity_date__range=(start_date, end_date))
        )
        student_aggregates[f'w{i}_new'] = Count(
            'id', filter=Q(created_at__gte=start_dt, created_at__lt=end_dt)
        )
        session_aggregates[f'w{i}_seconds'] = Sum(
            'duration_seconds', filter=Q(date__range=(start_date, end_date))
        )
        week_payment_filter = paid & Q(paid_at__gte=start_dt, paid_at__lt=end_dt)
        payment_aggregates[f'w{i}_revenue'] = Sum('amount_byn', filter=week_payment_filter)
        payment_aggregates[f'w{i}_count'] = Count('id', filter=week_payment_filter)

    students = Student.objects.aggregate(**student_aggregates)
    sessions = UserSessionLog.objects.aggregate(**session_aggregates)
    payments = PaymentOrder.objects.aggregate(**payment_aggregates)

    weekly_breakdown = []
    for i, (start_date, end_date) in enumerate(weeks[:8]):
        revenue = payments[f'w{i}_revenue'] or 0
        previous_revenue = payments[f'w{i + 1}_revenue'] or 0
        weekly_breakdown.append({
            'period': f'{start_date.strftime("%d.%m")} – {end_date.strftime("%d.%m.%Y")}',
            'wau': students[f'w{i}_active'],
            'wau_growth': _calc_growth(students[f'w{i}_active'], students[f'w{i + 1}_active']),
            'new_reg': students[f'w{i}_new'],
            'hours': round((sessions[f'w{i}_seconds'] or 0) / 3600, 1),
            'orders_count': payments[f'w{i}_count'],
            'revenue': revenue,
            'revenue_growth': _calc_growth(revenue, previous_revenue),
        })

    context = {
        'title': '📊 Аналитика и Метрики',
        'wau_curr': students['wau_curr'],
        'wau_growth': _calc_growth(students['wau_curr'], students['wau_prev']),
        'new_users_week_curr': students['new_week_curr'],
        'new_users_week_growth': _calc_growth(students['new_week_curr'], students['new_week_prev']),
        'hours_week_curr': round((sessions['week_curr'] or 0) / 3600, 1),
        'time_week_growth': _calc_growth(sessions['week_curr'] or 0, sessions['week_prev'] or 0),
        'count_week_curr': payments['week_curr_count'],
        'rev_week_curr': payments['week_curr_revenue'] or 0,
        'rev_week_growth': _calc_growth(payments['week_curr_revenue'] or 0, payments['week_prev_revenue'] or 0),
        'mau_curr': students['mau_curr'],
        'mau_growth': _calc_growth(students['mau_curr'], students['mau_prev']),
        'new_users_month_curr': students['new_month_curr'],
        'new_users_month_growth': _calc_growth(students['new_month_curr'], students['new_month_prev']),
        'hours_month_curr': round((sessions['month_curr'] or 0) / 3600, 1),
        'time_month_growth': _calc_growth(sessions['month_curr'] or 0, sessions['month_prev'] or 0),
        'count_month_curr': payments['month_curr_count'],
        'rev_month_curr': payments['month_curr_revenue'] or 0,
        'rev_month_growth': _calc_growth(payments['month_curr_revenue'] or 0, payments['month_prev_revenue'] or 0),
        'weekly_breakdown': weekly_breakdown,
        'total_students': students['total_students'],
        'pro_students': students['pro_students'],
        'total_revenue': payments['total_revenue'] or 0,
    }
    return render(request, 'admin/analytics.html', context)


def _calc_growth(curr, prev) -> dict:
    """Вычисляет процент прироста и его цвет/знак."""
    if prev == 0:
        if curr > 0:
            return {'val': '+100%', 'positive': True}
        return {'val': '0%', 'positive': True}

    diff = ((curr - prev) / prev) * 100
    return {'val': f'{diff:+.1f}%', 'positive': diff >= 0}
