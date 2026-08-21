#!/usr/bin/env python3
"""Скрипт для захвата реальных скриншотов фронтенда Telegram Mini App."""

import asyncio
import os
import http.server
import socketserver
import threading
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / 'frontend'
OUTPUT_DIR = ROOT / 'media' / 'presentation_screens'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Спин-ап сервер для статики фронтенда
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

async def capture():
    port = 8899
    handler = lambda *args, **kwargs: Handler(*args, **kwargs)
    httpd = socketserver.TCPServer(('127.0.0.1', port), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    url = f'http://127.0.0.1:{port}/index.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Настройка 390x844 (стандарт мобайл экрана в Telegram Mini App)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = await context.new_page()
        await page.goto(url)
        await page.wait_for_timeout(1000)

        # 1. Главный экран
        s1 = OUTPUT_DIR / 'screen_home.png'
        await page.screenshot(path=str(s1))
        print(f'Captured: {s1}')

        # 2. Вкладка Практика
        try:
            await page.click('[data-route="practice"]')
            await page.wait_for_timeout(500)
            s2 = OUTPUT_DIR / 'screen_practice.png'
            await page.screenshot(path=str(s2))
            print(f'Captured: {s2}')
        except Exception as e:
            print('Practice tab error:', e)

        # 3. Вкладка Статистика
        try:
            await page.click('[data-route="stats"]')
            await page.wait_for_timeout(500)
            s3 = OUTPUT_DIR / 'screen_stats.png'
            await page.screenshot(path=str(s3))
            print(f'Captured: {s3}')
        except Exception as e:
            print('Stats tab error:', e)

        # 4. Вкладка Рейтинг
        try:
            await page.click('[data-route="rating"]')
            await page.wait_for_timeout(500)
            s4 = OUTPUT_DIR / 'screen_rating.png'
            await page.screenshot(path=str(s4))
            print(f'Captured: {s4}')
        except Exception as e:
            print('Rating tab error:', e)

        # 5. Вкладка Семья / Родители
        try:
            await page.click('[data-route="family"]')
            await page.wait_for_timeout(500)
            s5 = OUTPUT_DIR / 'screen_family.png'
            await page.screenshot(path=str(s5))
            print(f'Captured: {s5}')
        except Exception as e:
            print('Family tab error:', e)

        await browser.close()
    httpd.shutdown()

if __name__ == '__main__':
    asyncio.run(capture())
