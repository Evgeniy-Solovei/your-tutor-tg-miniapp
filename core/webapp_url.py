"""Хелпер URL мини-приложения: AppSettings → env."""

from __future__ import annotations

import os


def get_web_app_url() -> str:
    """Синхронно: сначала AppSettings.web_app_url, иначе WEB_APP_URL из env."""
    try:
        from core.models import AppSettings

        app = AppSettings.get_settings()
        if app.web_app_url:
            return app.web_app_url.rstrip('/')
    except Exception:
        pass
    return (os.getenv('WEB_APP_URL') or '').rstrip('/')


async def aget_web_app_url() -> str:
    try:
        from core.models import AppSettings

        app = await AppSettings.aget_settings()
        if app.web_app_url:
            return app.web_app_url.rstrip('/')
    except Exception:
        pass
    return (os.getenv('WEB_APP_URL') or '').rstrip('/')
