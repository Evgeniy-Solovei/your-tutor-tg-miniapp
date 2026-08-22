"""Расширения OpenAPI для нестандартной Telegram Mini App авторизации."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class TelegramInitDataAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'core.telegram_auth.TelegramInitDataAuthentication'
    name = 'telegramInitData'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Telegram-Init-Data',
            'description': 'Подписанный Telegram WebApp initData.',
        }
