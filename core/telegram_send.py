"""Асинхронная безопасная отправка сообщений в Telegram с задержками, чанками и обработкой ошибок (FloodControl / Blocked)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from core.telegram_auth import get_bot_token

logger = logging.getLogger(__name__)


async def send_telegram_message(
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
    reply_markup: Any = None,
    on_blocked: Optional[Callable[[int], None]] = None,
) -> bool:
    """
    Отправка одиночного сообщения с поддержкой авто-повтора при TelegramRetryAfter.
    """
    token = get_bot_token()
    if not token or token.strip() in {'', 'your-telegram-bot-token'}:
        logger.error('TOKEN не задан — не могу отправить сообщение')
        return False

    bot = Bot(token=token)
    try:
        kwargs: Dict[str, Any] = {}
        if parse_mode:
            kwargs['parse_mode'] = parse_mode
        if reply_markup:
            kwargs['reply_markup'] = reply_markup

        while True:
            try:
                await bot.send_message(chat_id, text, **kwargs)
                return True
            except TelegramRetryAfter as e:
                wait_time = e.retry_after + 1
                logger.warning('Flood control limits reached. Waiting %s seconds for chat_id=%s', wait_time, chat_id)
                await asyncio.sleep(wait_time)
            except TelegramForbiddenError:
                logger.info('Пользователь %s заблокировал бота', chat_id)
                if on_blocked:
                    try:
                        on_blocked(chat_id)
                    except Exception as ex:
                        logger.exception('Ошибка в on_blocked callback: %s', ex)
                return False
            except TelegramBadRequest as e:
                logger.error('Ошибка формата сообщения chat_id=%s: %s', chat_id, e)
                return False
            except TelegramAPIError as e:
                logger.error('Telegram API error for chat_id=%s: %s', chat_id, e)
                return False
            except Exception as e:
                logger.exception('Непредвиденная ошибка при отправке chat_id=%s: %s', chat_id, e)
                return False
    finally:
        await bot.session.close()


async def batch_send_telegram_messages(
    items: List[Dict[str, Any]],
    *,
    batch_size: int = 25,
    delay_between_messages: float = 0.05,
    delay_between_batches: float = 1.0,
    on_blocked: Optional[Callable[[int], Any]] = None,
) -> Dict[str, int]:
    """
    Пакетная безошибочная асинхронная рассылка большого числа сообщений (до 20,000+).

    Каждая запись в items должна содержать:
      - 'chat_id': int
      - 'text': str
      - 'parse_mode': str (optional)
      - 'reply_markup': Any (optional)
    """
    token = get_bot_token()
    if not token or token.strip() in {'', 'your-telegram-bot-token'}:
        logger.error('TOKEN не задан — отмена пакетной рассылки')
        return {'sent': 0, 'failed': 0, 'blocked': 0}

    bot = Bot(token=token)
    sent_count = 0
    failed_count = 0
    blocked_count = 0

    try:
        total = len(items)
        logger.info('Запуск пакетной рассылки на %s получателей (batch_size=%s)...', total, batch_size)

        for i in range(0, total, batch_size):
            chunk = items[i : i + batch_size]

            for item in chunk:
                chat_id = item['chat_id']
                text = item['text']
                parse_mode = item.get('parse_mode')
                reply_markup = item.get('reply_markup')

                sent = False
                max_attempts = 5
                attempt = 0

                while attempt < max_attempts and not sent:
                    attempt += 1
                    try:
                        kwargs: Dict[str, Any] = {}
                        if parse_mode:
                            kwargs['parse_mode'] = parse_mode
                        if reply_markup:
                            kwargs['reply_markup'] = reply_markup

                        await bot.send_message(chat_id, text, **kwargs)
                        sent_count += 1
                        sent = True
                    except TelegramRetryAfter as e:
                        wait_seconds = e.retry_after + 1
                        logger.warning('Flood limits for chat_id=%s, wait %s sec', chat_id, wait_seconds)
                        await asyncio.sleep(wait_seconds)
                    except TelegramForbiddenError:
                        logger.info('Пользователь %s заблокировал бота', chat_id)
                        blocked_count += 1
                        if on_blocked:
                            try:
                                res = on_blocked(chat_id)
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception as ex:
                                logger.exception('Ошибка в on_blocked callback: %s', ex)
                        break
                    except TelegramBadRequest as e:
                        logger.error('Ошибка запроса chat_id=%s: %s', chat_id, e)
                        failed_count += 1
                        break
                    except Exception as e:
                        logger.error('Ошибка отправки chat_id=%s (попытка %s): %s', chat_id, attempt, e)
                        if attempt >= max_attempts:
                            failed_count += 1
                        else:
                            await asyncio.sleep(0.5)

                await asyncio.sleep(delay_between_messages)

            # Пауза между пачками для стабильности от спам-фильтров Telegram
            if i + batch_size < total:
                await asyncio.sleep(delay_between_batches)

    finally:
        await bot.session.close()

    logger.info('Пакетная рассылка завершена: отправлено=%s, ошибок=%s, заблокировали=%s', sent_count, failed_count, blocked_count)
    return {'sent': sent_count, 'failed': failed_count, 'blocked': blocked_count}
