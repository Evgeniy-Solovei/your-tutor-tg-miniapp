"""API мини-приложения: родители, коды, отчёты."""

from __future__ import annotations

from adrf.views import APIView
from rest_framework import status
from rest_framework.response import Response

from core.api import aget_student_by_tg, telegram_auth_classes
from core.telegram_auth import TelegramInitDataAuthentication, TelegramWebAppUser
from core.telegram_send import send_telegram_message
from students.models import Parent, ParentChildLink, Student
from students import parent_service


def _telegram_user(request) -> TelegramWebAppUser | None:
    user = getattr(request, 'telegram_user', None)
    return user if isinstance(user, TelegramWebAppUser) else None


async def _aget_parent_from_request(request) -> tuple[Parent | None, Response | None]:
    user = _telegram_user(request)
    if not user:
        return None, Response({'detail': 'Нужна авторизация Telegram'}, status=401)
    parent = await parent_service.get_or_create_parent(
        user.id,
        username=user.username or '',
        display_name=user.display_name or '',
    )
    return parent, None


class FamilyHubView(APIView):
    """
    Состояние вкладки «Семья»:
    - если пользователь ученик — код для родителя и привязанные родители;
    - если родитель — список привязанных детей.
    """

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def get(self, request):
        user = _telegram_user(request)
        if not user:
            return Response({'detail': 'Нужна авторизация Telegram'}, status=401)

        student = await (
            Student.objects.filter(tg_id=user.id, registration_completed=True).afirst()
        )
        invite_payload = None
        parents = []
        if student:
            invite = await parent_service.get_active_invite(student)
            if not invite:
                invite = await parent_service.issue_parent_invite(student)
            invite_payload = {
                'code': invite.code,
                'expires_at': invite.expires_at.isoformat(),
                'student_name': student.display_name,
            }
            async for link in ParentChildLink.objects.filter(student=student).select_related('parent'):
                p = link.parent
                parents.append({
                    'id': p.id,
                    'display_name': p.display_name or 'Родитель',
                })

        parent = await Parent.objects.filter(tg_id=user.id).afirst()
        children = []
        if parent:
            for child in await parent_service.list_children(parent):
                children.append(
                    {
                        'id': child.id,
                        'display_name': child.display_name,
                        'grade': child.grade,
                        'streak_days': child.streak_days,
                        'city_name': child.city.name if child.city_id else None,
                        'school_name': child.school.name if child.school_id else None,
                    }
                )

        return Response(
            {
                'telegram_id': user.id,
                'is_student': bool(student),
                'is_parent': bool(parent and children) or bool(parent),
                'invite': invite_payload,
                'children': children,
                'parents': parents,
                'periods': [
                    {'id': 'week', 'label': 'Эта неделя'},
                    {'id': 'month', 'label': 'Этот месяц'},
                    {'id': 'custom', 'label': 'Свой период'},
                ],
            }
        )


class ParentInviteIssueView(APIView):
    """Ученик создаёт/обновляет код для родителя."""

    authentication_classes = telegram_auth_classes()
    permission_classes = []

    async def post(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err
        invite = await parent_service.issue_parent_invite(student)
        return Response(
            {
                'code': invite.code,
                'expires_at': invite.expires_at.isoformat(),
                'message': 'Новый код готов. Покажи его родителю.',
            }
        )


class ParentLinkChildView(APIView):
    """Родитель вводит код ребёнка."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        parent, err = await _aget_parent_from_request(request)
        if err:
            return err
        code = (request.data.get('code') or '').strip()
        link, message = await parent_service.link_parent_by_code(parent, code)
        if not link:
            return Response({'detail': message}, status=status.HTTP_400_BAD_REQUEST)
        child = await Student.objects.select_related('city', 'school').aget(pk=link.student_id)
        return Response(
            {
                'message': message,
                'child': {
                    'id': child.id,
                    'display_name': child.display_name,
                    'grade': child.grade,
                },
            }
        )


class ParentSendReportView(APIView):
    """Собрать отчёт за период и отправить родителю в Telegram-бот."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        parent, err = await _aget_parent_from_request(request)
        if err:
            return err

        try:
            student_id = int(request.data.get('student_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'Укажи student_id'}, status=400)

        if not await parent_service.parent_has_child(parent, student_id):
            return Response({'detail': 'Этот ребёнок не привязан к тебе'}, status=403)

        period = (request.data.get('period') or 'week').strip().lower()
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')

        student = await Student.objects.aget(pk=student_id)
        try:
            text = await parent_service.build_parent_report(
                student,
                period=period,
                date_from=date_from,
                date_to=date_to,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        ok = await send_telegram_message(parent.tg_id, text, parse_mode=None)
        if not ok:
            return Response(
                {
                    'detail': (
                        'Не удалось отправить в Telegram. '
                        'Открой бота и нажми /start, затем попробуй снова.'
                    ),
                },
                status=502,
            )

        return Response(
            {
                'ok': True,
                'message': 'Отчёт отправлен тебе в бот.',
                'student_id': student_id,
                'period': period,
            }
        )


class ParentUnlinkChildView(APIView):
    """Отвязать ребёнка (по желанию родителя)."""

    authentication_classes = [TelegramInitDataAuthentication]
    permission_classes = []

    async def post(self, request):
        parent, err = await _aget_parent_from_request(request)
        if err:
            return err
        try:
            student_id = int(request.data.get('student_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'Укажи student_id'}, status=400)

        deleted, _ = await ParentChildLink.objects.filter(
            parent=parent, student_id=student_id
        ).adelete()
        if not deleted:
            return Response({'detail': 'Связь не найдена'}, status=404)
        return Response({'ok': True, 'message': 'Ребёнок отвязан'})
