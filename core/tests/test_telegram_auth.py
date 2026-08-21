"""Тесты HMAC Telegram WebApp initData."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from core.telegram_auth import validate_init_data


def make_init_data(user: dict, bot_token: str, *, auth_date: int | None = None) -> str:
    payload = {
        'auth_date': str(auth_date or int(time.time())),
        'user': json.dumps(user, separators=(',', ':')),
    }
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(payload.items()))
    secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    payload['hash'] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


class TelegramAuthTests(SimpleTestCase):
    @override_settings(TELEGRAM_BOT_TOKEN='123456:TEST')
    def test_valid_hash(self):
        init = make_init_data({'id': 42, 'first_name': 'Ivan'}, '123456:TEST')
        user = validate_init_data(init, bot_token='123456:TEST')
        self.assertEqual(user.id, 42)
        self.assertEqual(user.first_name, 'Ivan')

    @override_settings(TELEGRAM_BOT_TOKEN='123456:TEST')
    def test_tampered_hash(self):
        init = make_init_data({'id': 42, 'first_name': 'Ivan'}, '123456:TEST')
        bad = init.replace('Ivan', 'Hacker')
        with self.assertRaises(AuthenticationFailed):
            validate_init_data(bad, bot_token='123456:TEST')
