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
    await bot.set_my_commands(commands)


async def main() -> None:
    if not TOKEN or TOKEN.strip() in {'', 'your-telegram-bot-token'}:
        raise RuntimeError(
            'TOKEN не задан в .env. Добавь токен от @BotFather и запусти снова: python telegram.py'
        )

    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands()
    logging.info('Бот запущен (polling).')
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
