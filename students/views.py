from datetime import timedelta
import logging
import uuid
import httpx
from adrf.views import APIView
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from core.api import aget_student_by_tg, telegram_auth_classes
from core.services import student_can_practice
from core.telegram_auth import TelegramInitDataAuthentication, TelegramWebAppUser
from learning.services import get_or_create_daily_session, get_next_session_task, get_weak_topics
from students.models import PaymentOrder, Student, UserSessionLog
from students.serializers import StudentSerializer


class DevUsersView(APIView):
    """Список учеников для локального входа (только DEBUG + BYPASS)."""

    authentication_classes = []
    permission_classes = []

    async def get(self, request):
        from django.conf import settings as dj_settings

        if not (dj_settings.DEBUG and getattr(dj_settings, 'TELEGRAM_AUTH_BYPASS', False)):
            return Response({'detail': 'Только для локальной отладки'}, status=404)

        users = [
            {
                'tg_id': s.tg_id,
                'display_name': s.display_name,
                'registered': s.registration_completed,
            }
            async for s in Student.objects.order_by('display_name')[:50]
        ]
        return Response({'users': users, 'bypass': True})


class MeView(APIView):
    """Текущий пользователь из проверенного initData — без tg_id в URL."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def get(self, request):
        user = getattr(request, 'telegram_user', None)
        if not isinstance(user, TelegramWebAppUser):
            return Response(
                {
                    'detail': 'Нужна авторизация Telegram',
                    'hint': 'Локально: открой /app/?dev_tg_id=ТВОЙ_ID при TELEGRAM_AUTH_BYPASS=True',
                },
                status=401,
            )

        student = await (
            Student.objects.select_related('subject', 'exam_track', 'city', 'school')
            .filter(tg_id=user.id, registration_completed=True)
            .afirst()
        )
        from students.models import Parent, ParentChildLink

        parent = await Parent.objects.filter(tg_id=user.id).afirst()
        is_parent = bool(
            parent and await ParentChildLink.objects.filter(parent=parent).aexists()
        )

        if not student:
            return Response(
                {
                    'telegram': {
                        'id': user.id,
                        'display_name': user.display_name,
                        'username': user.username,
                    },
                    'registered': False,
                    'is_parent': is_parent,
                    'can_use_family': True,
                }
            )

        await student.update_activity_streak()
        serializer = StudentSerializer(student)
        data = await serializer.adata
        data['registered'] = True
        data['telegram'] = {
            'id': user.id,
            'display_name': user.display_name,
            'username': user.username,
        }
        data['city_name'] = student.city.name if student.city_id else None
        data['school_name'] = student.school.name if student.school_id else None
        data['subject_name'] = student.subject.name if student.subject_id else None
        data['is_parent'] = is_parent
        data['can_use_family'] = True
        return Response(data)


class StudentProfileView(APIView):
    """Профиль ученика для Mini App."""

    authentication_classes = telegram_auth_classes()

    @extend_schema(responses={200: StudentSerializer})
    async def get(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err
        await student.update_activity_streak()
        serializer = StudentSerializer(student)
        return Response(await serializer.adata)

    async def patch(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err
        data = request.data
        if 'notifications_enabled' in data:
            student.notifications_enabled = bool(data['notifications_enabled'])
            await student.asave(update_fields=['notifications_enabled'])
        serializer = StudentSerializer(student)
        return Response(await serializer.adata)


class StudentStatsView(APIView):
    """Статистика и слабые темы."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        from asgiref.sync import sync_to_async
        from django.db.models import Max, Sum, Value
        from django.db.models.functions import Coalesce
        from learning.models import DailySession

        weak = await get_weak_topics(student, limit=10)

        @sync_to_async
        def session_scores():
            return DailySession.objects.filter(student_id=student.id).aggregate(
                best_test=Coalesce(Max('test_score'), Value(0)),
                total_primary=Coalesce(Sum('primary_score'), Value(0)),
            )

        scores = await session_scores()
        return Response(
            {
                'xp': student.xp,
                'streak_days': student.streak_days,
                'is_pro': student.has_active_pro,
                'best_test_score': scores.get('best_test') or 0,
                'total_primary': scores.get('total_primary') or 0,
                'weak_topics': [
                    {
                        'topic_id': m.topic_id,
                        'topic_name': m.topic.name,
                        'mastery_score': m.mastery_score,
                        'wrong_count': m.wrong_count,
                    }
                    for m in weak
                ],
            }
        )


class DailySessionView(APIView):
    """Текущая ежедневная сессия для Mini App."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        can, reason = await student_can_practice(student)
        if not can:
            return Response({'can_practice': False, 'reason': reason})

        from learning.models import DailySession
        from learning.views import serialize_current_task

        # Активная тренировка (изложения и т.п.) важнее дневной сессии
        train = await (
            DailySession.objects.filter(
                student=student,
                status=DailySession.Status.IN_PROGRESS,
                kind=DailySession.Kind.TRAIN,
            )
            .order_by('-id')
            .afirst()
        )
        if train and await train.session_tasks.filter(is_answered=False).aexists():
            session = train
        else:
            session = await get_or_create_daily_session(student)

        next_task = await get_next_session_task(session)
        task_data = await serialize_current_task(next_task)
        content_available = bool(task_data) or (session.tasks_total or 0) > 0
        empty_reason = ''
        if not content_available:
            empty_reason = (
                f'Для {student.grade} класса заданий пока мало или сессия пуста. '
                f'Загляни позже — база пополняется.'
            )

        return Response(
            {
                'can_practice': True,
                'content_available': content_available,
                'empty_reason': empty_reason,
                'practice_grade': student.grade,
                'session_date': session.session_date,
                'status': session.status,
                'kind': session.kind,
                'mode': 'izlozhenie' if session.kind == DailySession.Kind.TRAIN else 'daily',
                'tasks_completed': session.tasks_completed,
                'tasks_total': session.tasks_total,
                'xp_earned': session.xp_earned,
                'primary_score': session.primary_score,
                'max_primary': session.max_primary,
                'test_score': session.test_score,
                'current_task': task_data,
            }
        )


class LeaderboardView(APIView):
    """Рейтинг по тестовому / первичному баллу: страна / город / школа."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request):
        from django.db.models import Max, Sum, Value
        from django.db.models.functions import Coalesce

        user = getattr(request, 'telegram_user', None)
        if not isinstance(user, TelegramWebAppUser):
            return Response({'detail': 'Нужна авторизация Telegram'}, status=401)

        me = await (
            Student.objects.select_related('city', 'school')
            .filter(tg_id=user.id, registration_completed=True)
            .afirst()
        )

        scope = request.query_params.get('scope', 'country')
        if scope not in {'country', 'city', 'school', 'grade'}:
            scope = 'country'

        period = request.query_params.get('period', 'week')
        if period not in {'week', 'month', 'all'}:
            period = 'week'

        city_id = request.query_params.get('city_id') or (me.city_id if me else None)
        school_id = request.query_params.get('school_id') or (me.school_id if me else None)

        def filters_payload(**extra):
            return {
                'has_city': bool(me and me.city_id),
                'has_school': bool(me and me.school_id),
                'city_name': me.city.name if me and me.city_id else None,
                'school_name': me.school.name if me and me.school_id else None,
                'city_id': me.city_id if me else None,
                'school_id': me.school_id if me else None,
                'grade': me.grade if me else None,
                'period': period,
                **extra,
            }

        qs = Student.objects.filter(registration_completed=True)
        title = 'Беларусь'
        empty_reason = ''

        if scope == 'grade':
            if me and me.grade:
                qs = qs.filter(grade=me.grade)
                title = f'{me.grade} класс'
            else:
                title = 'Мой класс'
        elif scope == 'city':
            if not city_id:
                return Response(
                    {
                        'scope': scope,
                        'title': 'Город',
                        'metric': 'test_score',
                        'entries': [],
                        'empty_reason': 'В профиле не указан город.',
                        'filters': filters_payload(),
                    }
                )
            qs = qs.filter(city_id=city_id)
            try:
                city_id = int(city_id)
            except (TypeError, ValueError):
                city_id = None
            if me and me.city_id == city_id:
                city = me.city
            else:
                from core.models import City

                city = await City.objects.filter(id=city_id).afirst() if city_id else None
            title = city.name if city else f'Город #{city_id}'
        elif scope == 'school':
            if not school_id:
                return Response(
                    {
                        'scope': scope,
                        'title': 'Школа',
                        'metric': 'test_score',
                        'entries': [],
                        'empty_reason': 'В профиле не указана школа.',
                        'filters': filters_payload(),
                    }
                )
            qs = qs.filter(school_id=school_id)
            try:
                school_id = int(school_id)
            except (TypeError, ValueError):
                school_id = None
            if me and me.school_id == school_id:
                school = me.school
            else:
                from core.models import School

                school = await School.objects.filter(id=school_id).afirst() if school_id else None
            title = school.name if school else f'Школа #{school_id}'

        from learning.leaderboard import get_or_create_active_league, week_bounds, month_bounds
        from learning.models import WeeklyLeague, DailySession
        from django.db.models import Q

        active_league = None
        if period != 'all':
            p_type = WeeklyLeague.PeriodType.MONTH if period == 'month' else WeeklyLeague.PeriodType.WEEK
            active_league = await get_or_create_active_league(p_type)

        if period == 'week':
            s_date, e_date = week_bounds()
            session_filter = Q(daily_sessions__session_date__gte=s_date, daily_sessions__session_date__lte=e_date)
        elif period == 'month':
            s_date, e_date = month_bounds()
            session_filter = Q(daily_sessions__session_date__gte=s_date, daily_sessions__session_date__lte=e_date)
        else:
            session_filter = Q()

        qs = qs.annotate(
            best_test=Coalesce(Max('daily_sessions__test_score', filter=session_filter), Value(0)),
            total_primary=Coalesce(Sum('daily_sessions__primary_score', filter=session_filter), Value(0)),
        ).order_by('-best_test', '-total_primary', '-xp', 'created_at')

        top = [
            {
                'display_name': s.display_name,
                'test_score': s.best_test,
                'primary_score': s.total_primary,
                'xp': s.xp,
                'streak_days': s.streak_days,
                'is_me': bool(me and s.id == me.id),
            }
            async for s in qs[:50]
        ]
        if not top and not empty_reason:
            empty_reason = 'Пока никого в этом рейтинге.'

        league_data = None
        if active_league:
            has_prizes = bool(
                active_league.prize_first_place or
                active_league.prize_second_place or
                active_league.prize_third_place or
                active_league.prizes_text
            )
            league_data = {
                'id': active_league.id,
                'title': active_league.title,
                'period_type': active_league.period_type,
                'week_start': str(active_league.week_start),
                'week_end': str(active_league.week_end),
                'has_prizes': has_prizes,
                'prize_first_place': active_league.prize_first_place,
                'prize_second_place': active_league.prize_second_place,
                'prize_third_place': active_league.prize_third_place,
                'prizes_text': active_league.prizes_text,
            }

        return Response(
            {
                'scope': scope,
                'title': title,
                'metric': 'test_score',
                'entries': top,
                'empty_reason': empty_reason,
                'filters': filters_payload(),
                'active_league': league_data,
            }
        )


KIND_LABELS = {
    'daily': 'На сегодня',
    'train': 'Тренировка',
    'variant': 'Вариант',
    'mistakes': 'Ошибки',
}


class ScoreHistoryView(APIView):
    """Все результаты сессий: от лучшего тестового балла к худшему, по 10."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, tg_id: int):
        from learning.models import DailySession

        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        page_size = 10

        from django.db.models import F

        qs = DailySession.objects.filter(student=student, max_primary__gt=0)
        total = await qs.acount()
        pages = max(1, (total + page_size - 1) // page_size) if total else 1
        page = min(page, pages)
        offset = (page - 1) * page_size

        rows = []
        async for s in qs.order_by(
            F('test_score').desc(nulls_last=True),
            '-primary_score',
            '-session_date',
            '-created_at',
        )[offset : offset + page_size]:
            rows.append(
                {
                    'id': s.id,
                    'date': s.session_date.isoformat(),
                    'kind': s.kind,
                    'kind_label': KIND_LABELS.get(s.kind, s.kind),
                    'test_score': s.test_score,
                    'primary_score': s.primary_score,
                    'max_primary': s.max_primary,
                    'tasks_completed': s.tasks_completed,
                    'tasks_total': s.tasks_total,
                    'status': s.status,
                }
            )

        return Response(
            {
                'page': page,
                'page_size': page_size,
                'pages': pages,
                'total': total,
                'results': rows,
            }
        )


class StreakDetailView(APIView):
    """Текущая серия дней и список дат подряд."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, tg_id: int):
        from datetime import timedelta

        from django.utils import timezone
        from learning.models import DailySession, TaskAttempt

        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        streak = student.streak_days or 0
        last = student.last_activity_date
        dates = []
        if streak > 0 and last:
            for i in range(streak):
                dates.append((last - timedelta(days=i)).isoformat())
            dates.sort()

        from asgiref.sync import sync_to_async

        @sync_to_async
        def recent_attempt_days():
            return [
                d.isoformat()
                for d in TaskAttempt.objects.filter(student=student).dates(
                    'created_at', 'day', order='DESC'
                )[:30]
            ]

        @sync_to_async
        def recent_session_days():
            return [
                d.isoformat()
                for d in DailySession.objects.filter(student=student, tasks_completed__gt=0)
                .values_list('session_date', flat=True)
                .distinct()
                .order_by('-session_date')[:30]
            ]

        active_dates = await recent_attempt_days()
        sessions_days = await recent_session_days()

        return Response(
            {
                'streak_days': streak,
                'last_activity_date': last.isoformat() if last else None,
                'streak_dates': dates,
                'recent_activity_dates': active_dates or sessions_days,
                'today': timezone.localdate().isoformat(),
            }
        )


class TariffsView(APIView):
    """Список тарифов + текущий план ученика."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request):
        from core.tariffs import TARIFFS, current_plan_id

        user = getattr(request, 'telegram_user', None)
        if not isinstance(user, TelegramWebAppUser):
            return Response({'detail': 'Нужна авторизация Telegram'}, status=401)

        student = await Student.objects.filter(
            tg_id=user.id, registration_completed=True
        ).afirst()
        current = current_plan_id(student) if student else 'free'

        plans = []
        for plan in TARIFFS:
            item = dict(plan)
            item['is_current'] = plan['id'] == current
            plans.append(item)

        return Response(
            {
                'currency': 'BYN',
                'current_plan_id': current,
                'plans': plans,
                'note': 'Оплата через bePaid / ЕРИП и банковские карты Беларуси.',
            }
        )


class DashboardView(APIView):
    """Дашборд успеваемости ученика для Mini App."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        from asgiref.sync import sync_to_async
        from django.db.models import Count, Q, Max, Sum, Value
        from django.db.models.functions import Coalesce
        from learning.models import TaskAttempt, TopicMastery, DailySession
        from knowledge.models import Section

        @sync_to_async
        def get_dashboard_stats():
            attempts = TaskAttempt.objects.filter(student=student)
            total = attempts.count()
            correct = attempts.filter(is_correct=True).count()
            accuracy = round((correct / total * 100)) if total > 0 else 0

            best_test = DailySession.objects.filter(student=student).aggregate(
                best=Coalesce(Max('test_score'), Value(0))
            )['best'] or 0

            # Разбивка по разделам предмета
            sections = []
            for sec in Section.objects.filter(exam_track_id=student.exam_track_id):
                topics = TopicMastery.objects.filter(student=student, topic__section=sec)
                t_count = topics.count()
                avg_mastery = 0
                if t_count > 0:
                    avg_mastery = round(sum(m.mastery_score for m in topics) / t_count * 100)
                sections.append({
                    'id': sec.id,
                    'title': sec.name,
                    'topics_count': t_count,
                    'mastery_percent': avg_mastery,
                })

            # Активность за последние 7 дней
            end_d = timezone.localdate()
            start_d = end_d - timedelta(days=6)
            daily_activity = []
            cur = start_d
            while cur <= end_d:
                day_attempts = attempts.filter(created_at__date=cur)
                d_total = day_attempts.count()
                d_correct = day_attempts.filter(is_correct=True).count()
                daily_activity.append({
                    'date': cur.strftime('%d.%m'),
                    'total': d_total,
                    'correct': d_correct,
                })
                cur += timedelta(days=1)

            return {
                'total_attempts': total,
                'correct_attempts': correct,
                'accuracy_percent': accuracy,
                'streak_days': student.streak_days,
                'xp': student.xp,
                'best_test_score': best_test,
                'sections': sections,
                'daily_activity': daily_activity,
            }

        stats = await get_dashboard_stats()
        return Response(stats)


import uuid
import json
import logging
from students.models import PaymentOrder
from core.telegram_send import send_telegram_message

logger = logging.getLogger(__name__)


class BePaidCheckoutView(APIView):
    """Генерация счёта на оплату bePaid (ЕРИП / Банковские карты)."""

    authentication_classes = telegram_auth_classes()

    async def post(self, request):
        user = getattr(request, 'telegram_user', None)
        if not isinstance(user, TelegramWebAppUser):
            return Response({'detail': 'Нужна авторизация Telegram'}, status=401)

        student = await Student.objects.filter(tg_id=user.id).afirst()
        if not student:
            return Response({'detail': 'Ученик не найден'}, status=404)

        plan_code = request.data.get('plan_code', 'pro_1m')
        plans = {
            'pro_1m': {'amount': 19.90, 'days': 30, 'title': 'Pro-подписка на 1 месяц'},
            'pro_3m': {'amount': 49.90, 'days': 90, 'title': 'Pro-подписка на 3 месяца'},
            'pro_12m': {'amount': 149.90, 'days': 365, 'title': 'Pro-подписка на 1 год'},
        }
        if plan_code not in plans:
            return Response({'detail': 'Неверный код тарифа'}, status=400)

        plan = plans[plan_code]
        order_id = f'PAY-{uuid.uuid4().hex[:12].upper()}'
        amount_cents = int(round(plan['amount'] * 100))

        shop_id = getattr(settings, 'BEPAID_SHOP_ID', '4225')
        secret_key = getattr(settings, 'BEPAID_SECRET_KEY', '3834fbef1fe6ea024ef77f5c79ec7ff1ba710ea6241c08c2f341afda8af4c1c4')
        test_mode = getattr(settings, 'BEPAID_TEST_MODE', True)

        checkout_url = f'https://checkout.bepaid.by/v2/checkout?token=test_{order_id}'
        bepaid_token = f'test_{order_id}'

        notification_url = request.build_absolute_uri('/api/tutor/payments/bepaid/webhook/').replace('http://', 'https://') if not settings.DEBUG else request.build_absolute_uri('/api/tutor/payments/bepaid/webhook/')
        return_url = request.build_absolute_uri('/app/').replace('http://', 'https://') if not settings.DEBUG else request.build_absolute_uri('/app/')

        payload = {
            "checkout": {
                "test": test_mode,
                "transaction_type": "payment",
                "attempts": 3,
                "notification_url": notification_url,
                "return_url": return_url,
                "order": {
                    "amount": amount_cents,
                    "currency": "BYN",
                    "description": f"{plan['title']} (Ученик: {student.display_name})",
                    "tracking_id": order_id,
                },
                "customer": {
                    "first_name": student.display_name or "Ученик",
                },
                "payment_method": {
                    "types": ["card", "erip"]
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    'https://checkout.bepaid.by/v2/checkout',
                    json=payload,
                    auth=(str(shop_id), str(secret_key)),
                    headers={'Accept': 'application/json', 'Content-Type': 'application/json'}
                )
                if res.status_code in (200, 201):
                    res_data = res.json().get('checkout', {})
                    bepaid_token = res_data.get('token', bepaid_token)
                    checkout_url = res_data.get('redirect_url', checkout_url)
        except Exception as e:
            logger.warning('bePaid API call exception: %s. Using fallback checkout URL.', e)

        order = await PaymentOrder.objects.acreate(
            order_id=order_id,
            student=student,
            plan_code=plan_code,
            amount_byn=plan['amount'],
            days=plan['days'],
            status=PaymentOrder.Status.PENDING,
            bepaid_checkout_url=checkout_url,
            bepaid_token=bepaid_token,
        )

        return Response({
            'order_id': order.order_id,
            'amount_byn': str(order.amount_byn),
            'days': order.days,
            'title': plan['title'],
            'checkout_url': checkout_url,
            'bepaid_token': bepaid_token,
        })


class BePaidWebhookView(APIView):
    """Webhook обработки уведомлений об оплате от bePaid."""

    permission_classes = []
    authentication_classes = []

    async def post(self, request):
        data = request.data or {}
        transaction = data.get('transaction', {})
        order_id = transaction.get('tracking_id') or data.get('order_id')
        status = transaction.get('status') or data.get('status')

        if not order_id:
            return Response({'detail': 'order_id missing'}, status=400)

        order = await PaymentOrder.objects.filter(order_id=order_id).select_related('student').afirst()
        if not order:
            return Response({'detail': 'Order not found'}, status=404)

        if status in ('successful', 'paid'):
            order.status = PaymentOrder.Status.PAID
            order.paid_at = timezone.now()
            await order.asave(update_fields=['status', 'paid_at'])

            # Активируем Pro ученику
            student = order.student
            student.is_pro = True
            base_date = student.pro_until if (student.pro_until and student.pro_until > timezone.now()) else timezone.now()
            student.pro_until = base_date + timedelta(days=order.days)
            await student.asave(update_fields=['is_pro', 'pro_until'])

            # Уведомление родителю/ученику в бот
            msg = (
                f'🎉 **Оплата успешно получена!**\n\n'
                f'Вам активирована **Pro-подписка** на **{order.days} дней**.\n'
                f'Доступны безлимитные упражнения, симулятор ЦТ/ЦЭ и ИИ-помощник!'
            )
            await send_telegram_message(student.tg_id, msg, parse_mode='Markdown')

        return Response({'status': 'ok'})


class PingSessionView(APIView):
    """Принимает пинги активности из Mini App и сохраняет общее время ученика."""

    authentication_classes = telegram_auth_classes()

    async def post(self, request):
        student = getattr(request, 'student', None)
        if not student:
            return Response({'detail': 'Unauthorized'}, status=401)

        try:
            duration = int(request.data.get('duration_seconds', 30))
        except (ValueError, TypeError):
            duration = 30

        if duration <= 0 or duration > 300:
            duration = 30

        today = timezone.localdate()
        log, created = await UserSessionLog.objects.aget_or_create(
            student=student,
            date=today,
            defaults={'duration_seconds': duration, 'session_count': 1},
        )
        if not created:
            log.duration_seconds += duration
            await log.asave(update_fields=['duration_seconds', 'updated_at'])

        if student.last_activity_date != today:
            student.last_activity_date = today
            await student.asave(update_fields=['last_activity_date', 'updated_at'])

        return Response({
            'status': 'ok',
            'today_total_seconds': log.duration_seconds,
        })