"""Безопасная раздача загруженных файлов через Django-контейнер."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.utils._os import safe_join
from django.views.decorators.http import require_GET


@require_GET
def media_file(request, path: str):
    """Отдать файл из MEDIA_ROOT, не позволяя выйти за его пределы."""
    try:
        full_path = Path(safe_join(settings.MEDIA_ROOT, path))
    except (SuspiciousFileOperation, ValueError, TypeError):
        raise Http404 from None

    if not full_path.is_file():
        raise Http404

    content_type, encoding = mimetypes.guess_type(str(full_path))
    response = FileResponse(
        full_path.open('rb'),
        content_type=content_type or 'application/octet-stream',
    )
    if encoding:
        response['Content-Encoding'] = encoding
    response['Cache-Control'] = 'public, max-age=604800'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
