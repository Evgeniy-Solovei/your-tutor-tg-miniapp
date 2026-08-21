#!/usr/bin/env python3
"""Скрипт снятия идеальных полных экранов приложения с двумя темами дизайна."""

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
    "tasks_completed": 3,
    "tasks_total": 5,
    "can_practice": True,
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
    "best_test_score": 88,
    "streak_days": 8,
    "total_tasks_solved": 145,
    "accuracy_percent": 82,
    "sections": [
        {"name": "Фонетика и графика", "progress": 95, "status": "Отлично (РИКЗ 95%)"},
        {"name": "Орфография суффиксов", "progress": 78, "status": "Хорошо (РИКЗ 78%)"},
        {"name": "Пунктуация в сложных предложениях", "progress": 42, "status": "Требует внимания (РИКЗ 42%)"}
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

mock_leaderboard_minsk = {
    "scope": "city",
    "city_name": "Минск",
    "items": [
        {"rank": 1, "name": "Алексей С.", "school": "СШ №14 г. Минск", "xp": 1450, "is_me": True},
        {"rank": 2, "name": "Елена В.", "school": "Лицей БГУ г. Минск", "xp": 1390, "is_me": False},
        {"rank": 3, "name": "Максим Т.", "school": "Гимназия №10 г. Минск", "xp": 1310, "is_me": False},
        {"rank": 4, "name": "София К.", "school": "Гимназия №50 г. Минск", "xp": 1240, "is_me": False},
        {"rank": 5, "name": "Илья Д.", "school": "СШ №199 г. Минск", "xp": 1180, "is_me": False},
        {"rank": 6, "name": "Данила П.", "school": "Гимназия №1 г. Минск", "xp": 1120, "is_me": False},
        {"rank": 7, "name": "Виктория Н.", "school": "СШ №42 г. Минск", "xp": 1050, "is_me": False}
    ]
}

mock_catalog = {
    "how_it_works": [
        "1. Выбери предмет и свой класс (1–11 класс) или трек ЦТ/ЦЭ.",
        "2. Проходи поурочные задания или варианты РИКЗ 2003–2025 гг.",
        "3. Получай разбор каждой ошибки от ИИ DeepSeek."
    ],
    "items": [
        {
            "id": 1,
            "name": "Русский язык",
            "tracks": [
                {"name": "Подготовка к ЦТ / ЦЭ 2026 (11 класс)", "desc": "220+ вариантов 2003–2025 гг., шкала РИКЗ 100 баллов, таймер 180 мин"},
                {"name": "Изложения и выпускной экзамен (9 класс)", "desc": "166 официальных текстов НИО с аудированием"},
                {"name": "Сборники упражнений (1–8 классы)", "desc": "Поурочные карточки с правилами и иллюстрациями"}
            ]
        },
        {
            "id": 2,
            "name": "Математика",
            "tracks": [
                {"name": "Подготовка к ЦТ / ЦЭ по математике", "desc": "Задачи частей А и Б, формула расчета баллов"}
            ]
        },
        {
            "id": 3,
            "name": "Белорусский язык",
            "tracks": [
                {"name": "ЦТ / ЦЭ Беларуская мова 2026", "desc": "Поўны банк заданняў РІКВ"}
            ]
        }
    ]
}

mock_tariffs = {
    "note": "Выбери тариф для комфортной подготовки к ЦЭ/ЦТ 2026",
    "plans": [
        {
            "id": "free",
            "name": "Старт (Free)",
            "price_label": "Бесплатно",
            "tagline": "3 задания в день для знакомства",
            "features": ["3 задания в день", "Базовая статистика", "Рейтинг школ"],
            "not_included": ["Симулятор ЦТ/ЦЭ 180 мин", "ИИ-объяснения DeepSeek", "Родительские отчёты"],
            "is_current": False
        },
        {
            "id": "pro",
            "name": "Pro Репетитор 🔥",
            "price_label": "19.90 BYN / мес",
            "tagline": "Полный безлимит и персональный ИИ",
            "features": [
                "Безлимит заданий на каждый день",
                "Симулятор ЦТ/ЦЭ с таймером 180 мин",
                "ИИ-разбор правил от DeepSeek",
                "Семейный кабинет для родителей",
                "Приоритетный доступ к розыгрышам"
            ],
            "not_included": [],
            "is_current": True
        }
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

async def capture():
    port = 8877
    handler = lambda *args, **kwargs: Handler(*args, **kwargs)
    httpd = socketserver.TCPServer(('127.0.0.1', port), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    url = f'http://127.0.0.1:{port}/index.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 412, 'height': 915},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = await context.new_page()

        async def handle_route(route, request):
            path = request.url
            if '/api/tutor/me/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_me))
            elif '/api/tutor/daily-session/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_daily))
            elif '/api/tutor/stats/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_stats))
            elif '/api/tutor/leaderboard/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_leaderboard_minsk))
            elif '/api/tutor/tariffs/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_tariffs))
            elif '/api/tutor/family/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_family))
            elif '/knowledge/catalog/' in path or '/catalog/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_catalog))
            else:
                await route.fulfill(status=200, content_type='application/json', body='{}')

        await page.route('**/api/tutor/**', handle_route)

        await page.goto(url)
        await page.wait_for_timeout(1000)

        # 1. Главный экран (Тема Вайб)
        await page.evaluate("localStorage.setItem('tutor_theme', 'vibe'); document.documentElement.setAttribute('data-theme', 'vibe');")
        await page.reload()
        await page.wait_for_timeout(500)
        s1 = OUTPUT_DIR / 'p_screen_home_vibe.png'
        await page.screenshot(path=str(s1), full_page=True)

        # 2. Курсы и Каталог программ (Тема Вайб - Полный рост)
        await page.click('.tab[data-route="courses"]')
        await page.wait_for_timeout(500)
        s2 = OUTPUT_DIR / 'p_screen_courses_full.png'
        await page.screenshot(path=str(s2), full_page=True)

        # 3. Практика (Тема Спокойная / Обычный вид)
        await page.evaluate("localStorage.setItem('tutor_theme', 'calm'); document.documentElement.setAttribute('data-theme', 'calm');")
        await page.reload()
        await page.click('.tab[data-route="practice"]')
        await page.wait_for_timeout(500)
        s3 = OUTPUT_DIR / 'p_screen_practice_calm.png'
        await page.screenshot(path=str(s3), full_page=True)

        # 4. Аналитика успеваемости (Подробная)
        await page.click('.tab[data-route="stats"]')
        await page.wait_for_timeout(500)
        s4 = OUTPUT_DIR / 'p_screen_stats_rich.png'
        await page.screenshot(path=str(s4), full_page=True)

        # 5. Рейтинг школ Минска (С реальной активностью)
        await page.click('.tab[data-route="rating"]')
        await page.wait_for_timeout(500)
        s5 = OUTPUT_DIR / 'p_screen_rating_minsk.png'
        await page.screenshot(path=str(s5), full_page=True)

        # 6. Экран Тарифов и Подписки Pro 19.90 BYN
        await page.click('.tab[data-route="home"]')
        await page.wait_for_timeout(300)
        await page.click('button[data-action="open-tariffs"]')
        await page.wait_for_timeout(500)
        s6 = OUTPUT_DIR / 'p_screen_tariffs_pro.png'
        await page.screenshot(path=str(s6), full_page=True)

        # 7. Семейный кабинет родителей
        await page.click('[data-action="close-panel"]')
        await page.wait_for_timeout(300)
        await page.click('.tab[data-route="family"]')
        await page.wait_for_timeout(500)
        s7 = OUTPUT_DIR / 'p_screen_family_parent.png'
        await page.screenshot(path=str(s7), full_page=True)

        await browser.close()
    httpd.shutdown()

    os.system(f'cp {OUTPUT_DIR}/*.png {ARTIFACT_DIR}/')
    print('Perfect presentation screens ready!')

if __name__ == '__main__':
    asyncio.run(capture())
