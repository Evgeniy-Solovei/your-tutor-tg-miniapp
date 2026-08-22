from pathlib import Path
import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET


FRONTEND_DIR = Path(settings.BASE_DIR) / 'frontend'


@require_GET
@xframe_options_exempt
def miniapp(request, path: str = ''):
    """
    Отдаёт файлы Mini App из каталога frontend.
    Поддерживает отдачу статики (.css, .js) и SPA-клиентский роутинг (возврат index.html для всех страниц).
    """
    clean_path = path.strip('/')
    if not clean_path:
        clean_path = 'index.html'

    root = FRONTEND_DIR.resolve()
    target = (FRONTEND_DIR / clean_path).resolve()

    # Защита от выхода за пределы каталога frontend
    if not str(target).startswith(str(root)):
        target = root / 'index.html'
        clean_path = 'index.html'

    # Если файл не существует (например, клиентский роут /app/practice) — отдаём index.html
    if not target.is_file():
        target = root / 'index.html'
        clean_path = 'index.html'

    content_type, _ = mimetypes.guess_type(str(target))
    if clean_path.endswith('.js'):
        content_type = 'text/javascript; charset=utf-8'
    elif clean_path.endswith('.css'):
        content_type = 'text/css; charset=utf-8'
    elif clean_path.endswith('.html'):
        content_type = 'text/html; charset=utf-8'

    response = FileResponse(target.open('rb'), content_type=content_type or 'application/octet-stream')
    # Telegram WebView агрессивно кеширует JS/CSS. Всегда перепроверяем версию,
    # иначе после деплоя пользователь может продолжать исполнять старый frontend.
    response['Cache-Control'] = 'no-cache, must-revalidate'
    response['Content-Security-Policy'] = (
        "frame-ancestors 'self' https://web.telegram.org https://telegram.org "
        'https://*.telegram.org'
    )
    return response
