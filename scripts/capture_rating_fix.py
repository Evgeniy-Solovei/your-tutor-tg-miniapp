#!/usr/bin/env python3
"""Скрипт захвата идеально наполненного экрана Рейтинга (с entries)."""

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
    "city": 1,
    "city_name": "г. Минск",
    "school": 14,
    "school_name": "СШ №14 г. Минск",
    "is_pro": True,
    "xp": 1450,
    "streak_days": 8,
    "registration_completed": True,
    "registered": True
}

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

# КОРРЕКТНАЯ СТРУКТУРА ДЛЯ renderRating() В app.js (с полем entries)
mock_leaderboard_correct = {
    "title": "г. Минск",
    "filters": {
        "has_city": True,
        "city_name": "г. Минск",
        "has_school": True,
        "school_name": "СШ №14 г. Минск"
    },
    "entries": [
        {"display_name": "Алексей С. · СШ №14", "test_score": 98, "is_me": True},
        {"display_name": "Елена В. · Лицей БГУ", "test_score": 94, "is_me": False},
        {"display_name": "Максим Т. · Гимназия №10", "test_score": 89, "is_me": False},
        {"display_name": "София К. · Гимназия №50", "test_score": 85, "is_me": False},
        {"display_name": "Илья Д. · СШ №199", "test_score": 82, "is_me": False},
        {"display_name": "Данила П. · Гимназия №1", "test_score": 78, "is_me": False},
        {"display_name": "Виктория Н. · СШ №42", "test_score": 75, "is_me": False},
        {"display_name": "Артём М. · Гимназия №7", "test_score": 71, "is_me": False},
        {"display_name": "Дарья О. · СШ №73", "test_score": 68, "is_me": False},
        {"display_name": "Никита К. · Лицей №1", "test_score": 64, "is_me": False}
    ]
}

async def capture():
    port = 8833
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
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_leaderboard_correct))
            else:
                await route.fulfill(status=200, content_type='application/json', body='{}')

        await page.route('**/api/tutor/**', handle_route)

        for theme in ['vibe', 'calm']:
            await page.goto(url)
            await page.evaluate(f"localStorage.setItem('tutor_theme', '{theme}'); document.documentElement.setAttribute('data-theme', '{theme}');")
            await page.reload()
            await page.wait_for_timeout(400)

            await page.click('.tab[data-route="rating"]')
            await page.wait_for_timeout(400)

            out_file = OUTPUT_DIR / f'ratio_target_rating_{theme}.png'
            await page.screenshot(path=str(out_file), full_page=True)
            print(f'Captured rating screen: {out_file.name}')

        await browser.close()
    httpd.shutdown()

    os.system(f'cp {OUTPUT_DIR}/ratio_target_rating_*.png {ARTIFACT_DIR}/')
    print('Rating screen successfully fixed and captured!')

if __name__ == '__main__':
    asyncio.run(capture())
