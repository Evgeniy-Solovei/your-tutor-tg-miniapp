#!/usr/bin/env python3
"""Скрипт генерации снимков ВСЕХ экранов приложения в ДВУХ темах дизайна (Вайб vs Спокойная/Обычная)."""

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

mock_leaderboard = {
    "scope": "city",
    "city_name": "Минск",
    "items": [
        {"rank": 1, "name": "Алексей С.", "school": "СШ №14 г. Минск", "xp": 1450, "is_me": True},
        {"rank": 2, "name": "Елена В.", "school": "Лицей БГУ г. Минск", "xp": 1390, "is_me": False},
        {"rank": 3, "name": "Максим Т.", "school": "Гимназия №10 г. Минск", "xp": 1310, "is_me": False},
        {"rank": 4, "name": "София К.", "school": "Гимназия №50 г. Минск", "xp": 1240, "is_me": False},
        {"rank": 5, "name": "Илья Д.", "school": "СШ №199 г. Минск", "xp": 1180, "is_me": False},
        {"rank": 6, "name": "Данила П.", "school": "Гимназия №1 г. Минск", "xp": 1120, "is_me": False}
    ]
}

mock_catalog_senior = {
    "how_it_works": [
        "🎓 Выпускные классы (10–11 классы)",
        "• Профильная подготовка к ЦТ/ЦЭ 2026",
        "• 220+ реальных вариантов РИКЗ 2003–2025 гг.",
        "• Таймер 180 минут и шкала перевода баллов (0–100)"
    ],
    "items": [
        {
            "id": 1,
            "name": "10–11 классы (ЦТ / ЦЭ)",
            "tracks": [
                {"name": "Русский язык — Полный банк ЦТ/ЦЭ", "desc": "13 500+ вопросов с ИИ-разбором DeepSeek"},
                {"name": "Математика — Части А и Б", "desc": "Алгебра, геометрия, формулы расчета баллов"},
                {"name": "Белорусский язык — ЦТ/ЦЭ", "desc": "Беларуская мова: усе варыянты РІКВ"}
            ]
        }
    ]
}

mock_catalog_junior = {
    "how_it_works": [
        "🎒 Начальная и средняя школа (1–9 классы)",
        "• 1–4 классы: игровое изучение с картинками",
        "• 5–8 классы: поурочные упражнения и контрольные",
        "• 9 класс: сборник 166 изложений и аудирование НИО"
    ],
    "items": [
        {
            "id": 2,
            "name": "1–9 классы (Школьная база)",
            "tracks": [
                {"name": "9 класс — Изложения (166 текстов)", "desc": "Официальный сборник Министерства образования РБ"},
                {"name": "5–8 классы — Упражнения и тренажёры", "desc": "Поурочные карточки по грамматике и пунктуации"},
                {"name": "1–4 классы — Начальная школа", "desc": "Интерактивные развивающие карточки с иллюстрациями"}
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
    port = 8866
    handler = lambda *args, **kwargs: Handler(*args, **kwargs)
    httpd = socketserver.TCPServer(('127.0.0.1', port), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    url = f'http://127.0.0.1:{port}/index.html'

    current_catalog = mock_catalog_senior

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
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_leaderboard))
            elif '/api/tutor/tariffs/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_tariffs))
            elif '/api/tutor/family/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_family))
            elif '/knowledge/catalog/' in path or '/catalog/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(current_catalog))
            else:
                await route.fulfill(status=200, content_type='application/json', body='{}')

        await page.route('**/api/tutor/**', handle_route)

        tasks = [
            # (Имя файла Vibe, Имя файла Calm, Маршрут, Доп действие)
            ('1_home', 'home', None),
            ('2_courses_senior', 'courses', 'senior'),
            ('3_courses_junior', 'courses', 'junior'),
            ('4_practice', 'practice', None),
            ('5_stats', 'stats', None),
            ('6_rating', 'rating', None),
            ('7_tariffs', 'tariffs', None),
            ('8_family', 'family', None),
        ]

        for base_name, route, sub in tasks:
            for theme in ['vibe', 'calm']:
                if sub == 'junior':
                    current_catalog = mock_catalog_junior
                else:
                    current_catalog = mock_catalog_senior

                await page.goto(url)
                await page.evaluate(f"localStorage.setItem('tutor_theme', '{theme}'); document.documentElement.setAttribute('data-theme', '{theme}');")
                await page.reload()
                await page.wait_for_timeout(400)

                if route == 'home':
                    pass
                elif route == 'tariffs':
                    await page.click('button[data-action="open-tariffs"]')
                    await page.wait_for_timeout(400)
                else:
                    await page.click(f'.tab[data-route="{route}"]')
                    await page.wait_for_timeout(400)

                out_file = OUTPUT_DIR / f'dual_{base_name}_{theme}.png'
                await page.screenshot(path=str(out_file), full_page=True)
                print(f'Captured: {out_file.name}')

        await browser.close()
    httpd.shutdown()

    os.system(f'cp {OUTPUT_DIR}/dual_*.png {ARTIFACT_DIR}/')
    print('All 16 dual theme screenshots captured and copied to artifacts!')

if __name__ == '__main__':
    asyncio.run(capture())
