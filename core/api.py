"""Общие хелперы API Mini App."""

from rest_framework.exceptions import APIException
from rest_framework.response import Response

from core.telegram_auth import require_matching_tg_id
from students.models import Student


async def aget_student_by_tg(request, tg_id: int) -> tuple[Student | None, Response | None]:
    try:
        require_matching_tg_id(request, tg_id)
    except APIException as exc:
        return None, Response({'detail': exc.detail}, status=exc.status_code)

    student = await Student.objects.filter(tg_id=tg_id, registration_completed=True).afirst()
    if not student:
        return None, Response(
            {'detail': 'Ученик не найден. Сначала пройди /start в боте.'},
            status=404,
        )
    return student, None


def telegram_auth_classes():
    from core.telegram_auth import TelegramInitDataAuthentication

    return [TelegramInitDataAuthentication]
