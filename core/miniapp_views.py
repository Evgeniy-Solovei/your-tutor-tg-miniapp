from pathlib import Path
import mimetypes

from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET


FRONTEND_DIR = Path(settings.BASE_DIR) / 'frontend'


def _inject_web_channel(html: str) -> str:
    """Помечает HTML как веб-сайт (не Telegram Mini App)."""
    marker = 'data-channel="web"'
    if marker in html:
        return html
    html = html.replace(
        '<html lang="ru"',
        '<html lang="ru" data-channel="web"',
        1,
    )
    html = html.replace(
        '<body>',
        '<body data-channel="web" class="channel-web">\n'
        '    <script>window.__TUTOR_CHANNEL__="web";</script>',
        1,
    )
    # Telegram SDK на чистом сайте не обязателен — оставляем, boot сам no-op
    return html


@require_GET
@xframe_options_exempt
def miniapp(request, path: str = ''):
    """
    Отдаёт файлы Mini App / веб-сайта из каталога frontend.
    Поддерживает статику (.css, .js) и SPA (index.html для неизвестных путей).
    """
    clean_path = path.strip('/')
    if not clean_path:
        clean_path = 'index.html'

    root = FRONTEND_DIR.resolve()
    target = (FRONTEND_DIR / clean_path).resolve()

    if not str(target).startswith(str(root)):
        target = root / 'index.html'
        clean_path = 'index.html'

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

    web_site = bool(getattr(settings, 'WEB_SITE_ENABLED', False))

    if clean_path.endswith('.html') and web_site:
        html = target.read_text(encoding='utf-8')
        html = _inject_web_channel(html)
        response = HttpResponse(html, content_type=content_type or 'text/html; charset=utf-8')
    else:
        response = FileResponse(
            target.open('rb'),
            content_type=content_type or 'application/octet-stream',
        )

    response['Cache-Control'] = 'no-cache, must-revalidate'
    if web_site:
        # Презентации / встраивание для инвестора
        response['Content-Security-Policy'] = "frame-ancestors *"
    else:
        response['Content-Security-Policy'] = (
            "frame-ancestors 'self' https://web.telegram.org https://telegram.org "
            'https://*.telegram.org'
        )
    return response
