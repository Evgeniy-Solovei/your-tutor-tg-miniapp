#!/usr/bin/env python3
"""Скрипт перехвата API и идеального снимка реального HTML/CSS фронтенда."""

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

mock_daily = {
    "session_id": 101,
    "title": "Задания дня (15 мин)",
    "completed_tasks": 3,
    "total_tasks": 5,
    "current_task": {
        "id": 501,
        "session_task_id": 1001,
        "task_number": "А4",
        "source_name": "ЦТ 2024, Вариант 2",
        "question": "Укажите номера слов, где на месте пропуска пишется буква Е:\n1) выго́р..вший\n2) недоумева́..мый\n3) зави́с..вший",
        "task_type": "single",
        "options": [
            {"id": "1", "text": "1, 2"},
            {"id": "2", "text": "2"},
            {"id": "3", "text": "1, 3"},
            {"id": "4", "text": "3"}
        ]
    }
}

mock_stats = {
    "total_tasks_solved": 145,
    "accuracy_percent": 82,
    "sections": [
        {"name": "Фонетика и графика", "progress": 95, "status": "Отлично"},
        {"name": "Орфография", "progress": 68, "status": "Хорошо"},
        {"name": "Синтаксис и пунктуация", "progress": 42, "status": "Требует внимания"}
    ],
    "weekly_activity": [
        {"day": "Пн", "tasks": 10},
        {"day": "Вт", "tasks": 15},
        {"day": "Ср", "tasks": 8},
        {"day": "Чт", "tasks": 12},
        {"day": "Пт", "tasks": 20},
        {"day": "Сб", "tasks": 25},
        {"day": "Вс", "tasks": 18}
    ]
}

mock_leaderboard = {
    "scope": "country",
    "items": [
        {"rank": 1, "name": "Алексей С.", "school": "СШ №14 г. Минск", "xp": 1450, "is_me": True},
        {"rank": 2, "name": "Мария К.", "school": "Гимназия №1 г. Гродно", "xp": 1380, "is_me": False},
        {"rank": 3, "name": "Дмитрий П.", "school": "СШ №5 г. Брест", "xp": 1290, "is_me": False},
        {"rank": 4, "name": "Елена В.", "school": "Лицей БГУ г. Минск", "xp": 1210, "is_me": False},
        {"rank": 5, "name": "Сергей М.", "school": "Гимназия №10 г. Гомель", "xp": 1150, "is_me": False}
    ]
}

mock_family = {
    "role": "parent",
    "children": [
        {
            "id": 1,
            "name": "Алексей (11 класс, СШ №14)",
            "streak": 8,
            "xp": 1450,
            "weekly_hours": 3.5,
            "accuracy": 82,
            "weak_topic": "Причастные обороты"
        }
    ]
}

mock_catalog = [
    {"id": 1, "title": "ЦТ / ЦЭ Русский язык 2025", "desc": "5 актуальных вариантов с таймером 180 мин"},
    {"id": 2, "title": "Сборник изложений (9 класс)", "desc": "166 эталонных текстов для экзамена"},
    {"id": 3, "title": "Тренажёр упражнений 1–11 класс", "desc": "Поурочная база заданий"}
]

async def capture():
    port = 8899
    handler = lambda *args, **kwargs: Handler(*args, **kwargs)
    httpd = socketserver.TCPServer(('127.0.0.1', port), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    url = f'http://127.0.0.1:{port}/index.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = await context.new_page()

        # Мокаем все API запросы
        async def handle_route(route, request):
            path = request.url
            if '/api/tutor/me/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_me))
            elif '/api/tutor/daily-session/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_daily))
            elif '/api/tutor/stats/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_stats))
            elif '/api/tutor/leaderboard/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_leaderboard))
            elif '/api/tutor/family/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_family))
            elif '/api/tutor/knowledge/catalog/' in path or '/knowledge/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_catalog))
            else:
                await route.fulfill(status=200, content_type='application/json', body='{}')

        await page.route('**/api/tutor/**', handle_route)

        await page.goto(url)
        await page.wait_for_timeout(1000)

        # 1. Главная
        s1 = OUTPUT_DIR / 'clean_html_home.png'
        await page.screenshot(path=str(s1))
        print(f'Captured: {s1}')

        # 2. Курсы
        try:
            await page.click('.tab[data-route="courses"]')
            await page.wait_for_timeout(500)
            s2 = OUTPUT_DIR / 'clean_html_courses.png'
            await page.screenshot(path=str(s2))
            print(f'Captured: {s2}')
        except Exception as e:
            print('Courses click:', e)

        # 3. Практика
        try:
            await page.click('.tab[data-route="practice"]')
            await page.wait_for_timeout(500)
            s3 = OUTPUT_DIR / 'clean_html_practice.png'
            await page.screenshot(path=str(s3))
            print(f'Captured: {s3}')
        except Exception as e:
            print('Practice click:', e)

        # 4. Статистика
        try:
            await page.click('.tab[data-route="stats"]')
            await page.wait_for_timeout(500)
            s4 = OUTPUT_DIR / 'clean_html_stats.png'
            await page.screenshot(path=str(s4))
            print(f'Captured: {s4}')
        except Exception as e:
            print('Stats click:', e)

        # 5. Рейтинг
        try:
            await page.click('.tab[data-route="rating"]')
            await page.wait_for_timeout(500)
            s5 = OUTPUT_DIR / 'clean_html_rating.png'
            await page.screenshot(path=str(s5))
            print(f'Captured: {s5}')
        except Exception as e:
            print('Rating click:', e)

        # 6. Семья
        try:
            await page.click('.tab[data-route="family"]')
            await page.wait_for_timeout(500)
            s6 = OUTPUT_DIR / 'clean_html_family.png'
            await page.screenshot(path=str(s6))
            print(f'Captured: {s6}')
        except Exception as e:
            print('Family click:', e)

        await browser.close()
    httpd.shutdown()

    os.system(f'cp {OUTPUT_DIR}/*.png {ARTIFACT_DIR}/')
    print('Clean HTML screenshots ready!')

if __name__ == '__main__':
    asyncio.run(capture())
