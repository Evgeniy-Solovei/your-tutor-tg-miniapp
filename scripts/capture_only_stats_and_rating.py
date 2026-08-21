#!/usr/bin/env python3
"""Скрипт обновления ТОЛЬКО 2 экранов (Аналитика успеваемости и Рейтинг школ) в двух темах."""

import asyncio
import http.server
import json
import os
import socketserver
import threading
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / 'frontend'
OUTPUT_DIR = ROOT / 'media' / 'presentation_screens'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path('/Users/solovey.e.v./.gemini/antigravity/brain/fad39013-b288-4b80-81e4-2467526a5cab')

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

mock_me = {
    "id": 1,
    "tg_id": 777842796,
    "display_name": "Алексей С.",
    "grade": 11,
    "goal": "ct",
    "subject": 1,
    "subject_name": "Русский язык",
    "exam_track": 4,
    "city": 1,
    "city_name": "Минск",
    "school": 14,
    "school_name": "СШ №14 г. Минск",
    "exam_year": 2026,
    "is_pro": True,
    "xp": 1450,
    "streak_days": 8,
    "registration_completed": True,
    "registered": True,
    "telegram": {"id": 777842796, "display_name": "Алексей", "username": "alex_by"},
    "can_use_family": True
}

# АНАЛИТИКА УСПЕВАЕМОСТИ С ЧЁТКИМИ СЛАБЫМИ ТЕМАМИ (НЕУСПЕВАЕМОСТЬ)
mock_stats_weak = {
    "best_test_score": 88,
    "streak_days": 8,
    "total_tasks_solved": 145,
    "accuracy_percent": 82,
    "weak_topics": [
        {"topic_name": "Пунктуация при вводных словах и обращениях (Раздел Б4)", "mastery_score": 0.35, "wrong_count": 12},
        {"topic_name": "Правописание Н / НН в причастиях и прилагательных", "mastery_score": 0.42, "wrong_count": 9},
        {"topic_name": "Правописание безударных гласных в корнях с чередованием", "mastery_score": 0.58, "wrong_count": 6}
    ]
}

# РЕЙТИНГ ШКОЛ С ТЕКУЩИМ ПОЛЬЗОВАТЕЛЕМ И МНОЖЕСТВОМ УЧАСТНИКОВ
mock_leaderboard_students = {
    "scope": "city",
    "city_name": "Минск",
    "items": [
        {"rank": 1, "name": "Алексей С. (Ты)", "school": "СШ №14 г. Минск", "xp": 1450, "is_me": True},
        {"rank": 2, "name": "Елена В.", "school": "Лицей БГУ г. Минск", "xp": 1390, "is_me": False},
        {"rank": 3, "name": "Максим Т.", "school": "Гимназия №10 г. Минск", "xp": 1310, "is_me": False},
        {"rank": 4, "name": "София К.", "school": "Гимназия №50 г. Минск", "xp": 1240, "is_me": False},
        {"rank": 5, "name": "Илья Д.", "school": "СШ №199 г. Минск", "xp": 1180, "is_me": False},
        {"rank": 6, "name": "Данила П.", "school": "Гимназия №1 г. Минск", "xp": 1120, "is_me": False},
        {"rank": 7, "name": "Виктория Н.", "school": "СШ №42 г. Минск", "xp": 1050, "is_me": False},
        {"rank": 8, "name": "Артём М.", "school": "Гимназия №7 г. Минск", "xp": 990, "is_me": False},
        {"rank": 9, "name": "Дарья О.", "school": "СШ №73 г. Минск", "xp": 940, "is_me": False},
        {"rank": 10, "name": "Никита К.", "school": "Лицей №1 г. Минск", "xp": 890, "is_me": False}
    ]
}

async def capture():
    port = 8844
    handler = lambda *args, **kwargs: Handler(*args, **kwargs)
    httpd = socketserver.TCPServer(('127.0.0.1', port), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    url = f'http://127.0.0.1:{port}/index.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 412, 'height': 890},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = await context.new_page()

        async def handle_route(route, request):
            path = request.url
            if '/api/tutor/me/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_me))
            elif '/api/tutor/stats/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_stats_weak))
            elif '/api/tutor/leaderboard/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_leaderboard_students))
            else:
                await route.fulfill(status=200, content_type='application/json', body='{}')

        await page.route('**/api/tutor/**', handle_route)

        targets = [
            ('stats', 'stats'),
            ('rating', 'rating')
        ]

        for base_name, route in targets:
            for theme in ['vibe', 'calm']:
                await page.goto(url)
                await page.evaluate(f"localStorage.setItem('tutor_theme', '{theme}'); document.documentElement.setAttribute('data-theme', '{theme}');")
                await page.reload()
                await page.wait_for_timeout(400)

                await page.click(f'.tab[data-route="{route}"]')
                await page.wait_for_timeout(400)

                out_file = OUTPUT_DIR / f'ratio_target_{base_name}_{theme}.png'
                await page.screenshot(path=str(out_file), full_page=True)
                print(f'Captured target screen: {out_file.name}')

        await browser.close()
    httpd.shutdown()

    os.system(f'cp {OUTPUT_DIR}/ratio_target_*.png {ARTIFACT_DIR}/')
    print('Updated target 2 screens in 2 themes (4 photos)!')

if __name__ == '__main__':
    asyncio.run(capture())
