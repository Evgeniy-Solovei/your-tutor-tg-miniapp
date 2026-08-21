"""Клиенты LLM: DeepSeek / Yandex / GigaChat (без OpenAI как основного)."""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    # для Yandex: Api-Key header вместо Bearer
    auth_header: str = 'Authorization'
    auth_prefix: str = 'Bearer'


_gigachat_token: str | None = None
_gigachat_token_expires: float = 0.0


def get_llm_config() -> LLMConfig | None:
    """
    AI_PROVIDER=deepseek|yandex|gigachat
    По умолчанию — deepseek.
    """
    provider = (os.getenv('AI_PROVIDER') or 'deepseek').strip().lower()

    if provider == 'deepseek':
        key = (
            os.getenv('DEEPSEEK_API_KEY')
            or os.getenv('AI_API_KEY')
            or ''
        ).strip()
        if not key:
            return None
        return LLMConfig(
            provider='deepseek',
            api_key=key,
            base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            model=os.getenv('AI_MODEL', 'deepseek-chat'),
        )

    if provider == 'yandex':
        key = (
            os.getenv('YANDEX_API_KEY')
            or os.getenv('AI_API_KEY')
            or ''
        ).strip()
        folder = (os.getenv('YANDEX_FOLDER_ID') or '').strip()
        if not key or not folder:
            return None
        raw_model = (os.getenv('AI_MODEL') or '').strip()
        # не тащим чужие имена моделей (deepseek-/GigaChat) в Yandex
        if (
            not raw_model
            or raw_model.startswith('deepseek')
            or raw_model.lower().startswith('gigachat')
            or raw_model.startswith('gpt-')
        ):
            model = f'gpt://{folder}/yandexgpt-lite'
        elif raw_model.startswith('gpt://'):
            model = raw_model
        else:
            model = f'gpt://{folder}/{raw_model}'
        return LLMConfig(
            provider='yandex',
            api_key=key,
            base_url=os.getenv(
                'YANDEX_BASE_URL',
                'https://llm.api.cloud.yandex.net/v1',
            ),
            model=model,
            auth_prefix='Api-Key',
        )

    if provider in {'gigachat', 'sber'}:
        # ключ авторизации = base64(client_id:client_secret) или готовый Authorization data
        auth_key = (
            os.getenv('GIGACHAT_AUTH_KEY')
            or os.getenv('AI_API_KEY')
            or ''
        ).strip()
        if not auth_key:
            return None
        return LLMConfig(
            provider='gigachat',
            api_key=auth_key,
            base_url=os.getenv(
                'GIGACHAT_BASE_URL',
                'https://gigachat.devices.sberbank.ru/api/v1',
            ),
            model=os.getenv('AI_MODEL', 'GigaChat'),
        )

    return None


async def _get_gigachat_access_token(auth_key: str) -> str | None:
    global _gigachat_token, _gigachat_token_expires
    now = time.time()
    if _gigachat_token and now < _gigachat_token_expires - 60:
        return _gigachat_token

    # auth_key может быть уже base64(client_id:secret) или сырой client_id:secret
    if ':' in auth_key and not auth_key.startswith('ey'):
        auth_b64 = base64.b64encode(auth_key.encode()).decode()
    else:
        auth_b64 = auth_key

    oauth_url = os.getenv(
        'GIGACHAT_OAUTH_URL',
        'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
    )
    scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'RqUID': os.urandom(16).hex(),
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    }
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.post(oauth_url, headers=headers, data={'scope': scope})
            resp.raise_for_status()
            data = resp.json()
            token = data.get('access_token')
            if not token:
                return None
            # expires_at в ms или expires_in
            exp = data.get('expires_at')
            if exp and exp > 10_000_000_000:
                _gigachat_token_expires = exp / 1000.0
            else:
                _gigachat_token_expires = now + float(data.get('expires_in', 1500))
            _gigachat_token = token
            return token
    except Exception:
        return None


async def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 700,
) -> tuple[str, str]:
    """
    Возвращает (text, model_name). Пустой text = ошибка/пустой ответ.
    """
    cfg = get_llm_config()
    if not cfg:
        return '', ''

    if cfg.provider == 'gigachat':
        text = await _gigachat_chat(cfg, system=system, user=user, temperature=temperature, max_tokens=max_tokens)
        return text, cfg.model

    # DeepSeek / Yandex — OpenAI-compatible SDK
    try:
        from openai import AsyncOpenAI

        if cfg.provider == 'yandex':
            # Yandex Cloud: Authorization: Api-Key <key>
            client = AsyncOpenAI(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                default_headers={'Authorization': f'Api-Key {cfg.api_key}'},
            )
        else:
            client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

        kwargs = {
            'model': cfg.model,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
        }
        # DeepSeek V4 иногда шлёт thinking — выключаем если поддерживается
        if cfg.provider == 'deepseek':
            kwargs['extra_body'] = {'thinking': {'type': 'disabled'}}

        response = await client.chat.completions.create(**kwargs)
        text = (response.choices[0].message.content or '').strip()
        return text, f'{cfg.provider}:{cfg.model}'
    except Exception:
        # fallback без extra_body
        try:
            from openai import AsyncOpenAI

            if cfg.provider == 'yandex':
                client = AsyncOpenAI(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                    default_headers={'Authorization': f'Api-Key {cfg.api_key}'},
                )
            else:
                client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
            response = await client.chat.completions.create(
                model=cfg.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ],
            )
            text = (response.choices[0].message.content or '').strip()
            return text, f'{cfg.provider}:{cfg.model}'
        except Exception:
            return '', cfg.model


async def _gigachat_chat(
    cfg: LLMConfig,
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    token = await _get_gigachat_access_token(cfg.api_key)
    if not token:
        return ''
    payload = {
        'model': cfg.model,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            resp = await client.post(
                f'{cfg.base_url.rstrip("/")}/chat/completions',
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return (data['choices'][0]['message']['content'] or '').strip()
    except Exception:
        return ''
