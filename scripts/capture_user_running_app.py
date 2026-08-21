#!/usr/bin/env python3
"""Скрипт снятия полных, некоротких скриншотов запущенного пользователем приложения."""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / 'media' / 'presentation_screens'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path('/Users/solovey.e.v./.gemini/antigravity/brain/fad39013-b288-4b80-81e4-2467526a5cab')

async def main():
    url = 'http://127.0.0.1:3000/app/?dev_tg_id=777842796'
    print(f'Navigating to {url}...')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 412, 'height': 915}, # Высокий мобайл экран
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            extra_http_headers={'ngrok-skip-browser-warning': 'true'}
        )
        page = await context.new_page()

        await page.goto(url)
        await page.wait_for_timeout(2000)

        # 1. Главная
        s1 = OUTPUT_DIR / 'full_screen_home.png'
        await page.screenshot(path=str(s1), full_page=True)
        print(f'Captured: {s1}')

        # 2. Курсы
        try:
            await page.click('[data-route="courses"]')
            await page.wait_for_timeout(1000)
            s2 = OUTPUT_DIR / 'full_screen_courses.png'
            await page.screenshot(path=str(s2), full_page=True)
            print(f'Captured: {s2}')
        except Exception as e:
            print('Courses click error:', e)

        # 3. Практика
        try:
            await page.click('[data-route="practice"]')
            await page.wait_for_timeout(1000)
            s3 = OUTPUT_DIR / 'full_screen_practice.png'
            await page.screenshot(path=str(s3), full_page=True)
            print(f'Captured: {s3}')
        except Exception as e:
            print('Practice click error:', e)

        # 4. Статистика
        try:
            await page.click('[data-route="stats"]')
            await page.wait_for_timeout(1000)
            s4 = OUTPUT_DIR / 'full_screen_stats.png'
            await page.screenshot(path=str(s4), full_page=True)
            print(f'Captured: {s4}')
        except Exception as e:
            print('Stats click error:', e)

        # 5. Рейтинг
        try:
            await page.click('[data-route="rating"]')
            await page.wait_for_timeout(1000)
            s5 = OUTPUT_DIR / 'full_screen_rating.png'
            await page.screenshot(path=str(s5), full_page=True)
            print(f'Captured: {s5}')
        except Exception as e:
            print('Rating click error:', e)

        # 6. Семья
        try:
            await page.click('[data-route="family"]')
            await page.wait_for_timeout(1000)
            s6 = OUTPUT_DIR / 'full_screen_family.png'
            await page.screenshot(path=str(s6), full_page=True)
            print(f'Captured: {s6}')
        except Exception as e:
            print('Family click error:', e)

        await browser.close()

    os.system(f'cp {OUTPUT_DIR}/*.png {ARTIFACT_DIR}/')
    print('Screenshots successfully captured and copied to artifacts!')

if __name__ == '__main__':
    asyncio.run(main())
