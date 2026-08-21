#!/usr/bin/env python3
"""Скрипт для захвата реальных и красивых экранов Mini App."""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / 'media' / 'presentation_screens'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path('/Users/solovey.e.v./.gemini/antigravity/brain/fad39013-b288-4b80-81e4-2467526a5cab')

async def main():
    env = os.environ.copy()
    env['TELEGRAM_AUTH_BYPASS'] = 'True'
    env['ALLOWED_HOSTS'] = '*'
    proc = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000'],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 390, 'height': 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )
            page = await context.new_page()

            url = 'http://127.0.0.1:8000/app/?dev_tg_id=777842796'
            print(f'Navigating to {url}...')
            await page.goto(url)
            await page.wait_for_timeout(2500)

            # 1. Главный экран
            s1 = OUTPUT_DIR / 'real_screen_home.png'
            await page.screenshot(path=str(s1))
            print(f'Captured: {s1}')

            # 2. Курсы
            try:
                await page.click('button[data-route="courses"]')
                await page.wait_for_timeout(1500)
                s2 = OUTPUT_DIR / 'real_screen_courses.png'
                await page.screenshot(path=str(s2))
                print(f'Captured: {s2}')
            except Exception as e:
                print('Error courses:', e)

            # 3. Практика
            try:
                await page.click('button[data-route="practice"]')
                await page.wait_for_timeout(1500)
                s3 = OUTPUT_DIR / 'real_screen_practice.png'
                await page.screenshot(path=str(s3))
                print(f'Captured: {s3}')
            except Exception as e:
                print('Error practice:', e)

            # 4. Статистика
            try:
                await page.click('button[data-route="stats"]')
                await page.wait_for_timeout(1500)
                s4 = OUTPUT_DIR / 'real_screen_stats.png'
                await page.screenshot(path=str(s4))
                print(f'Captured: {s4}')
            except Exception as e:
                print('Error stats:', e)

            # 5. Рейтинг
            try:
                await page.click('button[data-route="rating"]')
                await page.wait_for_timeout(1500)
                s5 = OUTPUT_DIR / 'real_screen_rating.png'
                await page.screenshot(path=str(s5))
                print(f'Captured: {s5}')
            except Exception as e:
                print('Error rating:', e)

            # 6. Семья
            try:
                await page.click('button[data-route="family"]')
                await page.wait_for_timeout(1500)
                s6 = OUTPUT_DIR / 'real_screen_family.png'
                await page.screenshot(path=str(s6))
                print(f'Captured: {s6}')
            except Exception as e:
                print('Error family:', e)

            await browser.close()
    finally:
        proc.terminate()
        print('Server stopped.')

    os.system(f'cp {OUTPUT_DIR}/*.png {ARTIFACT_DIR}/')
    print('Screenshots copied.')

if __name__ == '__main__':
    asyncio.run(main())
