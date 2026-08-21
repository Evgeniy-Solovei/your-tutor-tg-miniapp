"""Проверка Telegram WebApp initData (HMAC-SHA256), как в skillbox_tap."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework import authentication, exceptions


@dataclass(frozen=True)
class TelegramWebAppUser:
    """Пользователь из проверенного initData."""

    id: int
    first_name: str = ''
    last_name: str = ''
    username: str = ''
    language_code: str = ''
    is_premium: bool = False

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        name = f'{self.first_name} {self.last_name}'.strip()
        return name or self.username or str(self.id)


def get_bot_token() -> str:
    return (os.getenv('TOKEN') or getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '').strip()


def validate_init_data(
    init_data: str,
    *,
    bot_token: str | None = None,
    max_age_seconds: int = 86400,
) -> TelegramWebAppUser:
    """
    Алгоритм официальный:
    secret = HMAC_SHA256(key=\"WebAppData\", msg=bot_token)
    hash = HMAC_SHA256(key=secret, msg=data_check_string)
    """
    token = (bot_token or get_bot_token()).strip()
    if not token:
        raise exceptions.AuthenticationFailed('Bot token не настроен')

    if not init_data or not isinstance(init_data, str):
        raise exceptions.AuthenticationFailed('Missing Telegram-Init-Data')

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop('hash', None)
    if not received_hash:
        raise exceptions.AuthenticationFailed('Missing hash')

    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise exceptions.AuthenticationFailed('Invalid Telegram hash')

    auth_date_raw = pairs.get('auth_date')
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError as exc:
            raise exceptions.AuthenticationFailed('Invalid auth_date') from exc
        if max_age_seconds and abs(time.time() - auth_date) > max_age_seconds:
            raise exceptions.AuthenticationFailed('Telegram initData expired')

    user_raw = pairs.get('user')
    if not user_raw:
        raise exceptions.AuthenticationFailed('Missing user in initData')

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise exceptions.AuthenticationFailed('Invalid user JSON') from exc

    tg_id = user.get('id')
    if not tg_id:
        raise exceptions.AuthenticationFailed('Missing user.id')

    return TelegramWebAppUser(
        id=int(tg_id),
        first_name=user.get('first_name') or '',
        last_name=user.get('last_name') or '',
        username=user.get('username') or '',
        language_code=user.get('language_code') or '',
        is_premium=bool(user.get('is_premium')),
    )


class TelegramInitDataAuthentication(authentication.BaseAuthentication):
    """
    Ожидает заголовок Telegram-Init-Data (как в skillbox middleware).
    В DEBUG можно включить TELEGRAM_AUTH_BYPASS=1 и Telegram-Dev-User: <tg_id>.
    """

    header = 'HTTP_TELEGRAM_INIT_DATA'
    bypass_header = 'HTTP_TELEGRAM_DEV_USER'

    def authenticate(self, request):
        bypass = (
            getattr(settings, 'TELEGRAM_AUTH_BYPASS', False)
            or os.getenv('TELEGRAM_AUTH_BYPASS', '').lower() in {'1', 'true', 'yes'}
        )
        if bypass and settings.DEBUG:
            raw = request.META.get(self.bypass_header) or request.query_params.get('dev_tg_id')
            if raw:
                try:
                    tg_id = int(raw)
                except (TypeError, ValueError) as exc:
                    raise exceptions.AuthenticationFailed('Invalid Telegram-Dev-User') from exc
                user = TelegramWebAppUser(id=tg_id, first_name='Dev')
                request.telegram_user = user
                return (user, 'dev-bypass')

        init_data = request.META.get(self.header) or request.headers.get('Telegram-Init-Data')
        if not init_data:
            # Также принимаем Authorization: tma <initData> (удобно для фронта)
            auth = request.headers.get('Authorization', '')
            if auth.lower().startswith('tma '):
                init_data = auth[4:].strip()

        if not init_data:
            return None

        user = validate_init_data(init_data)
        request.telegram_user = user
        return (user, init_data)


def require_matching_tg_id(request, tg_id: int) -> TelegramWebAppUser:
    """Не даём подставить чужой tg_id в URL."""
    user = getattr(request, 'telegram_user', None) or getattr(request, 'user', None)
    if not isinstance(user, TelegramWebAppUser):
        raise exceptions.NotAuthenticated('Нужна авторизация Telegram Mini App')
    if int(user.id) != int(tg_id):
        raise exceptions.PermissionDenied('tg_id не совпадает с initData')
    return user
