"""Аналитический дашборд для админки (Unfold Admin)."""

from datetime import timedelta

from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from students.models import PaymentOrder, Student, UserSessionLog


def admin_analytics_view(request):
    """Отображает метрики WAU, MAU, время в Mini App, выручку и прирост WoW/MoM."""
    today = timezone.localdate()

    # --- 1. РАСЧЕТ ДАННЫХ ПО НЕДЕЛЯМ (WoW) ---
    # Текущая неделя (последние 7 дней)
    week_curr_start = today - timedelta(days=6)
    week_prev_start = today - timedelta(days=13)
    week_prev_end = today - timedelta(days=7)

    # WAU (Unique Active Users)
    wau_curr = Student.objects.filter(last_activity_date__gte=week_curr_start).count()
    wau_prev = Student.objects.filter(
        last_activity_date__range=[week_prev_start, week_prev_end]
    ).count()
    wau_growth = _calc_growth(wau_curr, wau_prev)

    # Новые регистрации
    new_users_week_curr = Student.objects.filter(created_at__date__gte=week_curr_start).count()
    new_users_week_prev = Student.objects.filter(
        created_at__date__range=[week_prev_start, week_prev_end]
    ).count()
    new_users_week_growth = _calc_growth(new_users_week_curr, new_users_week_prev)

    # Время в приложении (в секундах)
    sec_week_curr = UserSessionLog.objects.filter(date__gte=week_curr_start).aggregate(
        total=Sum('duration_seconds')
    )['total'] or 0
    sec_week_prev = UserSessionLog.objects.filter(
        date__range=[week_prev_start, week_prev_end]
    ).aggregate(total=Sum('duration_seconds'))['total'] or 0
    time_week_growth = _calc_growth(sec_week_curr, sec_week_prev)

    # Оплаты и Выручка
    paid_orders_week_curr = PaymentOrder.objects.filter(
        status=PaymentOrder.Status.PAID, paid_at__date__gte=week_curr_start
    )
    rev_week_curr = paid_orders_week_curr.aggregate(total=Sum('amount_byn'))['total'] or 0
    count_week_curr = paid_orders_week_curr.count()

    paid_orders_week_prev = PaymentOrder.objects.filter(
        status=PaymentOrder.Status.PAID,
        paid_at__date__range=[week_prev_start, week_prev_end],
    )
    rev_week_prev = paid_orders_week_prev.aggregate(total=Sum('amount_byn'))['total'] or 0
    rev_week_growth = _calc_growth(rev_week_curr, rev_week_prev)

    # --- 2. РАСЧЕТ ДАННЫХ ПО МЕСЯЦАМ (MoM) ---
    # Текущий месяц (30 дней)
    month_curr_start = today - timedelta(days=29)
    month_prev_start = today - timedelta(days=59)
    month_prev_end = today - timedelta(days=30)

    # MAU (Monthly Active Users)
    mau_curr = Student.objects.filter(last_activity_date__gte=month_curr_start).count()
    mau_prev = Student.objects.filter(
        last_activity_date__range=[month_prev_start, month_prev_end]
    ).count()
    mau_growth = _calc_growth(mau_curr, mau_prev)

    # Новые регистрации за месяц
    new_users_month_curr = Student.objects.filter(created_at__date__gte=month_curr_start).count()
    new_users_month_prev = Student.objects.filter(
        created_at__date__range=[month_prev_start, month_prev_end]
    ).count()
    new_users_month_growth = _calc_growth(new_users_month_curr, new_users_month_prev)

    # Время за месяц
    sec_month_curr = UserSessionLog.objects.filter(date__gte=month_curr_start).aggregate(
        total=Sum('duration_seconds')
    )['total'] or 0
    sec_month_prev = UserSessionLog.objects.filter(
        date__range=[month_prev_start, month_prev_end]
    ).aggregate(total=Sum('duration_seconds'))['total'] or 0
    time_month_growth = _calc_growth(sec_month_curr, sec_month_prev)

    # Выручка за месяц
    paid_orders_month_curr = PaymentOrder.objects.filter(
        status=PaymentOrder.Status.PAID, paid_at__date__gte=month_curr_start
    )
    rev_month_curr = paid_orders_month_curr.aggregate(total=Sum('amount_byn'))['total'] or 0
    count_month_curr = paid_orders_month_curr.count()

    paid_orders_month_prev = PaymentOrder.objects.filter(
        status=PaymentOrder.Status.PAID,
        paid_at__date__range=[month_prev_start, month_prev_end],
    )
    rev_month_prev = paid_orders_month_prev.aggregate(total=Sum('amount_byn'))['total'] or 0
    rev_month_growth = _calc_growth(rev_month_curr, rev_month_prev)

    # --- 3. ТАБЛИЦА ПО НЕДЕЛЯМ (ПОСЛЕДНИЕ 8 НЕДЕЛЬ) ---
    weekly_breakdown = []
    for i in range(8):
        w_start = today - timedelta(days=(i * 7) + 6)
        w_end = today - timedelta(days=i * 7)
        prev_w_start = w_start - timedelta(days=7)
        prev_w_end = w_end - timedelta(days=7)

        wau = Student.objects.filter(
            last_activity_date__range=[w_start, w_end]
        ).count()
        p_wau = Student.objects.filter(
            last_activity_date__range=[prev_w_start, prev_w_end]
        ).count()

        new_reg = Student.objects.filter(created_at__date__range=[w_start, w_end]).count()
        dur_sec = UserSessionLog.objects.filter(date__range=[w_start, w_end]).aggregate(
            t=Sum('duration_seconds')
        )['t'] or 0

        p_orders = PaymentOrder.objects.filter(
            status=PaymentOrder.Status.PAID, paid_at__date__range=[w_start, w_end]
        )
        rev = p_orders.aggregate(t=Sum('amount_byn'))['t'] or 0
        p_rev = PaymentOrder.objects.filter(
            status=PaymentOrder.Status.PAID, paid_at__date__range=[prev_w_start, prev_w_end]
        ).aggregate(t=Sum('amount_byn'))['t'] or 0

        weekly_breakdown.append({
            'period': f'{w_start.strftime("%d.%m")} – {w_end.strftime("%d.%m.%Y")}',
            'wau': wau,
            'wau_growth': _calc_growth(wau, p_wau),
            'new_reg': new_reg,
            'hours': round(dur_sec / 3600, 1),
            'orders_count': p_orders.count(),
            'revenue': rev,
            'revenue_growth': _calc_growth(rev, p_rev),
        })

    context = {
        'title': '📊 Аналитика и Метрики',
        # Неделя
        'wau_curr': wau_curr,
        'wau_growth': wau_growth,
        'new_users_week_curr': new_users_week_curr,
        'new_users_week_growth': new_users_week_growth,
        'hours_week_curr': round(sec_week_curr / 3600, 1),
        'time_week_growth': time_week_growth,
        'count_week_curr': count_week_curr,
        'rev_week_curr': rev_week_curr,
        'rev_week_growth': rev_week_growth,
        # Месяц
        'mau_curr': mau_curr,
        'mau_growth': mau_growth,
        'new_users_month_curr': new_users_month_curr,
        'new_users_month_growth': new_users_month_growth,
        'hours_month_curr': round(sec_month_curr / 3600, 1),
        'time_month_growth': time_month_growth,
        'count_month_curr': count_month_curr,
        'rev_month_curr': rev_month_curr,
        'rev_month_growth': rev_month_growth,
        # Таблицы
        'weekly_breakdown': weekly_breakdown,
        # Общие цифры
        'total_students': Student.objects.count(),
        'pro_students': Student.objects.filter(is_pro=True).count(),
        'total_revenue': PaymentOrder.objects.filter(status=PaymentOrder.Status.PAID).aggregate(
            t=Sum('amount_byn')
        )['t'] or 0,
    }
    return render(request, 'admin/analytics.html', context)


def _calc_growth(curr, prev) -> dict:
    """Вычисляет процент прироста и его цвет/знак."""
    if prev == 0:
        if curr > 0:
            return {'val': '+100%', 'positive': True}
        return {'val': '0%', 'positive': True}

    diff = ((curr - prev) / prev) * 100
    formatted = f'{diff:+.1f}%'
    return {
        'val': formatted,
        'positive': diff >= 0,
    }
