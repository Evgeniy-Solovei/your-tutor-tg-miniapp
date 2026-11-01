import asyncio
import logging
import os
import sys

import django
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutor_bot.settings')
django.setup()

from bot.handlers import router

TOKEN = os.getenv('TOKEN')
WEB_APP_URL = os.getenv('WEB_APP_URL', 'http://localhost:8000')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(router)


async def set_commands():
    commands = [
        BotCommand(command='start', description='Начать / регистрация'),
        BotCommand(command='help', description='Помощь'),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as exc:
        logging.warning('Не удалось установить команды бота: %s', exc)


async def main() -> None:
    if not TOKEN or TOKEN.strip() in {'', 'your-telegram-bot-token'}:
        raise RuntimeError(
            'TOKEN не задан в .env. Добавь токен от @BotFather и запусти снова: python telegram.py'
        )

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as exc:
        logging.warning('Ошибка при удалении вебхука: %s', exc)

    await set_commands()
    logging.info('🤖 Бот успешно инициализирован. Запуск отказоустойчивого polling...')

    retry_delay = 2
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=['message', 'callback_query'],
                handle_signals=False,
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            logging.info('🛑 Остановка бота по сигналу завершения...')
            break
        except Exception as exc:
            logging.error(
                '⚠️ Сбой соединения в polling-цикле: %s. Автоматический перезапуск через %s сек...',
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
        else:
            retry_delay = 2


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        stream=sys.stdout,
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info('Процесс бота завершён.')
