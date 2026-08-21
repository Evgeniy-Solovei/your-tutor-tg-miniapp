"""География (поиск городов и школ), регистрация и конфигурация."""

from __future__ import annotations

import re
from adrf.views import APIView
from rest_framework import status
from rest_framework.response import Response

from core.api import telegram_auth_classes
from core.models import AppSettings, City, School
from core.telegram_auth import TelegramInitDataAuthentication, TelegramWebAppUser
from students.models import Parent, Student
from students.registration_service import register_or_update_student
from students.serializers import StudentSerializer


def _tg_user(request) -> TelegramWebAppUser | None:
    u = getattr(request, 'telegram_user', None)
    return u if isinstance(u, TelegramWebAppUser) else None


class PublicConfigView(APIView):
    authentication_classes = []
    permission_classes = []

    async def get(self, request):
        app = await AppSettings.aget_settings()
        return Response({
            'max_daily_xp': app.max_daily_xp,
            'web_app_url': app.web_app_url,
            'free_ai_explanations_enabled': app.free_ai_explanations_enabled,
        })


class WebAppUrlSettingsView(APIView):
    async def post(self, request):
        url = (request.data.get('url') or '').strip().rstrip('/')
        if url and not (url.startswith('http://') or url.startswith('https://')):
            return Response({'detail': 'Укажи полный URL с http:// или https://'}, status=400)

        app = await AppSettings.aget_settings()
        app.web_app_url = url
        await app.asave(update_fields=['web_app_url', 'updated_at'])
        return Response({
            'web_app_url': app.web_app_url,
            'mini_app_url': f'{url}/app/' if url else '',
            'message': 'Сохранено. Перезапусти telegram.py, чтобы кнопка бота подхватила URL.',
        })


class CitySearchView(APIView):
    authentication_classes = []
    permission_classes = []

    async def get(self, request):
        raw_q = (request.query_params.get('q') or '').strip()
        clean_q = re.sub(r'^(г\.|город|пгт|пос[её]лок|аг\.|агрогородок)\s+', '', raw_q, flags=re.I).strip()
        limit = min(int(request.query_params.get('limit') or 20), 40)

        if not await City.objects.filter(is_active=True).aexists():
            from django.core.management import call_command
            call_command('seed_geo')

        qs = City.objects.filter(is_active=True)
        if clean_q:
            qs = qs.filter(name__icontains=clean_q)
        elif raw_q:
            qs = qs.filter(name__icontains=raw_q)

        cities = [
            {'id': c.id, 'name': c.name, 'region': c.region}
            async for c in qs.order_by('name')[:limit]
        ]
        return Response({'results': cities, 'q': raw_q})


class SchoolSearchView(APIView):
    authentication_classes = []
    permission_classes = []

    async def get(self, request, city_id: int):
        q = (request.query_params.get('q') or '').strip()
        limit = min(int(request.query_params.get('limit') or 20), 40)
        city = await City.objects.filter(id=city_id, is_active=True).afirst()
        if not city:
            city = await City.objects.filter(is_active=True).afirst()
            if not city:
                from django.core.management import call_command
                call_command('seed_geo')
                city = await City.objects.filter(is_active=True).afirst()

        if not city:
            return Response({'results': [], 'city': {'id': city_id, 'name': ''}, 'q': q})

        qs = School.objects.filter(city_id=city.id, is_active=True)
        if not await qs.aexists():
            # Запасные школы для небольших НП
            for n in (1, 2, 3, 5):
                await School.objects.aget_or_create(
                    city=city, name=f'Средняя школа №{n}', defaults={'is_active': True}
                )
            await School.objects.aget_or_create(
                city=city, name=f'Гимназия №1 г. {city.name}', defaults={'is_active': True}
            )
            qs = School.objects.filter(city_id=city.id, is_active=True)

        if q:
            qs = qs.filter(name__icontains=q)

        schools = [
            {'id': s.id, 'name': s.name, 'city_id': s.city_id}
            async for s in qs.order_by('name')[:limit]
        ]
        return Response({'results': schools, 'city': {'id': city.id, 'name': city.name}, 'q': q})


class RegisterView(APIView):
    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        user = _tg_user(request)
        if not user:
            return Response({'detail': 'Нужна авторизация Telegram'}, status=401)

        payload = request.data if isinstance(request.data, dict) else {}
        role = payload.get('role') or 'student'

        # Если регистрируется родитель
        if role == 'parent':
            from students import parent_service
            display_name = (payload.get('display_name') or '').strip() or user.display_name or 'Родитель'
            parent = await parent_service.get_or_create_parent(
                user.id,
                username=user.username or '',
                display_name=display_name,
            )
            return Response({
                'registered': True,
                'is_parent': True,
                'display_name': parent.display_name,
                'telegram': {
                    'id': user.id,
                    'display_name': user.display_name,
                    'username': user.username,
                }
            })

        try:
            student = await register_or_update_student(
                tg_id=user.id,
                username=user.username or '',
                payload=payload,
                require_geo=False,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        student = await (
            Student.objects.select_related('subject', 'exam_track', 'city', 'school')
            .aget(pk=student.pk)
        )
        serializer = StudentSerializer(student)
        data = await serializer.adata
        data['registered'] = True
        data['telegram'] = {
            'id': user.id,
            'display_name': user.display_name,
            'username': user.username,
        }
        return Response(data)


class ProfileUpdateView(APIView):
    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        user = _tg_user(request)
        if not user:
            return Response({'detail': 'Нужна авторизация Telegram'}, status=401)

        payload = request.data if isinstance(request.data, dict) else {}
        role = payload.get('role') or 'student'

        if role == 'parent':
            from students import parent_service
            display_name = (payload.get('display_name') or '').strip() or user.display_name or 'Родитель'
            parent = await parent_service.get_or_create_parent(
                user.id,
                username=user.username or '',
                display_name=display_name,
            )
            return Response({
                'registered': True,
                'is_parent': True,
                'display_name': parent.display_name,
            })

        try:
            student = await register_or_update_student(
                tg_id=user.id,
                username=user.username or '',
                payload=payload,
                require_geo=False,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        student = await (
            Student.objects.select_related('subject', 'exam_track', 'city', 'school')
            .aget(pk=student.pk)
        )
        serializer = StudentSerializer(student)
        data = await serializer.adata
        return Response(data)
