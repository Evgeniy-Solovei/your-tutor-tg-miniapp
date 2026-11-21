"""Хелпер URL мини-приложения: AppSettings → env → fallback."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os

DEFAULT_WEB_APP_URL = 'https://your-tutor.live-dev.by'
_cached_url: str | None = None


def get_web_app_url() -> str:
    """Синхронно: сначала AppSettings.web_app_url, иначе WEB_APP_URL из env, иначе DEFAULT."""
    global _cached_url
    if _cached_url:
        return _cached_url

    env_url = (os.getenv('WEB_APP_URL') or '').strip().rstrip('/')
    if env_url:
        _cached_url = env_url
        return _cached_url

    try:
        from core.models import AppSettings

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            with ThreadPoolExecutor(max_workers=1) as pool:
                app = pool.submit(AppSettings.get_settings).result(timeout=2)
                if app and app.web_app_url:
                    _cached_url = app.web_app_url.strip().rstrip('/')
                    return _cached_url
        else:
            app = AppSettings.get_settings()
            if app and app.web_app_url:
                _cached_url = app.web_app_url.strip().rstrip('/')
                return _cached_url
    except Exception:
        pass

    return DEFAULT_WEB_APP_URL


async def aget_web_app_url() -> str:
    global _cached_url
    if _cached_url:
        return _cached_url

    env_url = (os.getenv('WEB_APP_URL') or '').strip().rstrip('/')
    if env_url:
        _cached_url = env_url
        return _cached_url

    try:
        from core.models import AppSettings

        app = await AppSettings.aget_settings()
        if app and app.web_app_url:
            _cached_url = app.web_app_url.strip().rstrip('/')
            return _cached_url
    except Exception:
        pass

    return DEFAULT_WEB_APP_URL
