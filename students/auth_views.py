"""Аутентификация для веб-версии платформы и связывание с Telegram."""

from __future__ import annotations

import re
import secrets
import time
from datetime import timedelta

from adrf.views import APIView
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from core.telegram_auth import TelegramInitDataAuthentication, TelegramWebAppUser
from students.models import Student
from students.registration_service import resolve_subject_and_track
from students.serializers import StudentSerializer

LOGIN_REGEX = re.compile(r'^[a-zA-Z0-9_.\-]{3,50}$')


def _get_client_ip(request) -> str:
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


class WebRegisterView(APIView):
    """Регистрация нового пользователя на веб-сайте по логину и паролю."""

    authentication_classes = []
    permission_classes = []

    async def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        login = str(data.get('login') or '').strip()
        password = str(data.get('password') or '').strip()
        display_name = str(data.get('display_name') or '').strip()[:100]

        if not login or not LOGIN_REGEX.match(login):
            return Response(
                {'detail': 'Логин должен быть от 3 до 50 символов (буквы, цифры, _, -, .).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(password) < 6:
            return Response(
                {'detail': 'Пароль должен содержать не менее 6 символов.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not display_name:
            display_name = login

        try:
            grade = int(data.get('grade') or 11)
            if grade < 1 or grade > 11:
                grade = 11
        except (TypeError, ValueError):
            grade = 11

        goal = str(data.get('goal') or Student.Goal.IMPROVE).strip().lower()
        if goal not in Student.Goal.values:
            goal = Student.Goal.CT if grade == 11 else Student.Goal.IMPROVE

        # Проверка уникальности логина
        if await Student.objects.filter(web_login__iexact=login).aexists():
            return Response(
                {'detail': 'Пользователь с таким логином уже существует. Выберите другой логин.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject, track = await resolve_subject_and_track(grade, goal=goal)

        # Синтетический tg_id в диапазоне 9_000_000_000_000+
        base_id = 9_000_000_000_000
        for _ in range(10):
            candidate_id = base_id + secrets.randbelow(900_000_000) + int(time.time() * 1000) % 1_000_000
            if not await Student.objects.filter(tg_id=candidate_id).aexists():
                synthetic_tg_id = candidate_id
                break
        else:
            synthetic_tg_id = base_id + int(time.time() * 1000)

        web_token = secrets.token_hex(32)

        student = Student(
            tg_id=synthetic_tg_id,
            web_login=login,
            display_name=display_name,
            grade=grade,
            goal=goal,
            subject=subject,
            exam_track=track,
            registration_completed=True,
            web_token=web_token,
        )
        student.set_password(password)
        await student.asave()

        # Кэшируем токен для мгновенной валидации
        cache_key = f'web_token:{web_token}'
        try:
            await cache.aset(
                cache_key,
                (student.tg_id, student.display_name, student.username or ''),
                timeout=86400 * 30,
            )
        except Exception:
            pass

        serializer = StudentSerializer(student)
        student_data = await serializer.adata

        return Response(
            {
                'token': web_token,
                'student': student_data,
                'channel': 'web',
            },
            status=status.HTTP_201_CREATED,
        )


class WebLoginView(APIView):
    """Вход на веб-сайте по логину и паролю."""

    authentication_classes = []
    permission_classes = []

    async def post(self, request):
        ip = _get_client_ip(request)
        rate_key = f'web_login_attempts_{ip}'

        attempts = await cache.aget(rate_key, 0)
        if attempts >= 10:
            return Response(
                {'detail': 'Слишком много неудачных попыток входа. Пожалуйста, подождите 5 минут.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        data = request.data if isinstance(request.data, dict) else {}
        login = str(data.get('login') or '').strip()
        password = str(data.get('password') or '').strip()

        if not login or not password:
            return Response(
                {'detail': 'Укажите логин и пароль.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = await (
            Student.objects.select_related('subject', 'exam_track', 'city', 'school')
            .filter(web_login__iexact=login)
            .afirst()
        )

        if not student or not student.check_password(password):
            try:
                await cache.aset(rate_key, attempts + 1, timeout=300)
            except Exception:
                pass
            return Response(
                {'detail': 'Неверный логин или пароль.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            await cache.adelete(rate_key)
        except Exception:
            pass

        web_token = secrets.token_hex(32)
        student.web_token = web_token
        await student.asave(update_fields=['web_token', 'updated_at'])

        cache_key = f'web_token:{web_token}'
        try:
            await cache.aset(
                cache_key,
                (student.tg_id, student.display_name, student.username or ''),
                timeout=86400 * 30,
            )
        except Exception:
            pass

        serializer = StudentSerializer(student)
        student_data = await serializer.adata

        return Response(
            {
                'token': web_token,
                'student': student_data,
                'channel': 'web',
            }
        )


class WebLogoutView(APIView):
    """Завершение веб-сессии."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        auth = request.headers.get('Authorization', '') or request.META.get('HTTP_AUTHORIZATION', '')
        if auth.lower().startswith('bearer '):
            token = auth[7:].strip()
            if token:
                try:
                    await cache.adelete(f'web_token:{token}')
                except Exception:
                    pass

        user = getattr(request, 'telegram_user', None)
        if isinstance(user, TelegramWebAppUser):
            await Student.objects.filter(tg_id=user.id).aupdate(web_token=None)

        return Response({'ok': True})


class TelegramLinkIssueView(APIView):
    """Генерация одноразового кода для связывания веб-аккаунта с Telegram-ботом."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        user = getattr(request, 'telegram_user', None)
        if not isinstance(user, TelegramWebAppUser):
            return Response({'detail': 'Требуется авторизация.'}, status=status.HTTP_401_UNAUTHORIZED)

        student = await Student.objects.filter(tg_id=user.id).afirst()
        if not student:
            return Response({'detail': 'Ученик не найден.'}, status=status.HTTP_404_NOT_FOUND)

        code = f"TUT-{secrets.token_hex(2).upper()}"
        student.telegram_link_code = code
        student.telegram_link_expires = timezone.now() + timedelta(minutes=15)
        await student.asave(update_fields=['telegram_link_code', 'telegram_link_expires', 'updated_at'])

        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'tutor_by_bot')
        deeplink = f"https://t.me/{bot_username}?start=link_{code}"

        return Response({
            'code': code,
            'bot_username': bot_username,
            'deeplink': deeplink,
            'expires_in_minutes': 15,
        })


class TelegramUnlinkView(APIView):
    """Отвязка аккаунта от Telegram (возврат к синтетическому tg_id)."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        user = getattr(request, 'telegram_user', None)
        if not isinstance(user, TelegramWebAppUser):
            return Response({'detail': 'Требуется авторизация.'}, status=status.HTTP_401_UNAUTHORIZED)

        student = await Student.objects.filter(tg_id=user.id).afirst()
        if not student:
            return Response({'detail': 'Ученик не найден.'}, status=status.HTTP_404_NOT_FOUND)

        if not student.is_telegram_linked:
            return Response({'ok': True, 'is_telegram_linked': False})

        base_id = 9_000_000_000_000
        new_tg_id = base_id + secrets.randbelow(900_000_000) + int(time.time() * 1000) % 1_000_000
        student.tg_id = new_tg_id
        student.username = ''
        await student.asave(update_fields=['tg_id', 'username', 'updated_at'])

        if student.web_token:
            cache_key = f'web_token:{student.web_token}'
            try:
                await cache.aset(
                    cache_key,
                    (student.tg_id, student.display_name, student.username),
                    timeout=86400 * 30,
                )
            except Exception:
                pass

        return Response({'ok': True, 'is_telegram_linked': False, 'tg_id': new_tg_id})


class TelegramWebSessionCreateView(APIView):
    """Создание временной сессии для авторизации на сайте через Telegram-бота."""

    authentication_classes = []
    permission_classes = []

    async def post(self, request):
        ip = _get_client_ip(request)
        rate_key = f'tg_auth_create_rate:{ip}'
        try:
            cnt = await cache.aget(rate_key) or 0
            if cnt >= 20:
                return Response(
                    {'detail': 'Слишком много запросов на вход через Telegram. Попробуйте через минуту.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            await cache.aset(rate_key, cnt + 1, timeout=60)
        except Exception:
            pass

        session_id = f"AUTH-{secrets.token_hex(3).upper()}"
        cache_key = f"tg_auth_session:{session_id}"
        session_data = {
            'status': 'pending',
            'created_at': time.time(),
            'ip': ip,
        }
        try:
            await cache.aset(cache_key, session_data, timeout=300)
        except Exception:
            return Response(
                {'detail': 'Сервис кэширования временно недоступен.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'tutor_by_bot') or 'tutor_by_bot'
        deeplink = f"https://t.me/{bot_username}?start=auth_{session_id}"

        return Response({
            'session_id': session_id,
            'bot_username': bot_username,
            'deeplink': deeplink,
            'command': f"/auth {session_id}",
            'expires_in_seconds': 300,
        })


class TelegramWebSessionCheckView(APIView):
    """Проверка статуса сессии авторизации через Telegram-бота."""

    authentication_classes = []
    permission_classes = []

    async def get(self, request, session_id: str):
        session_id = str(session_id or '').strip().upper()
        if not session_id or len(session_id) > 40:
            return Response({'status': 'expired'})

        cache_key = f"tg_auth_session:{session_id}"
        try:
            session_data = await cache.aget(cache_key)
        except Exception:
            session_data = None

        if not session_data or not isinstance(session_data, dict):
            return Response({'status': 'expired'})

        if session_data.get('status') == 'confirmed':
            token = session_data.get('token')
            student = session_data.get('student')
            try:
                await cache.adelete(cache_key)
            except Exception:
                pass
            return Response({
                'status': 'confirmed',
                'token': token,
                'student': student,
            })

        return Response({'status': 'pending'})
