#!/usr/bin/env python3
"""Скрипт генерации идеальных экранов с сохранёнными пропорциями без искажений."""

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
        "reading_text": "(1) Осень в этом году выдалась невероятно тёплой и солнечной. (2) Берёзы вдоль лесной тропинки стояли в золотом уборе, тихо роняя листья на влажную траву. (3) В воздухе пахло сосновой хвоей, сухими грибами и свежим утренним туманом. (4) На опушке леса мы сделали небольшую остановку, чтобы полюбоваться панорамой озера. (5) День постепенно угасал, но солнце всё ещё согревало своими ласковыми лучами.",
        "question": "Прочитайте текст выше. Укажите номера предложений, в которых есть однородные сказуемые:",
        "task_type": "single",
        "options": [
            {"id": "1", "text": "2, 4"},
            {"id": "2", "text": "1, 3"},
            {"id": "3", "text": "2, 5"},
            {"id": "4", "text": "3, 4"}
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

# МНОГО ПОЛЬЗОВАТЕЛЕЙ В РЕЙТИНГЕ ШКОЛ
mock_leaderboard_many = {
    "scope": "city",
    "city_name": "Минск",
    "items": [
        {"rank": 1, "name": "Алексей С.", "school": "СШ №14 г. Минск", "xp": 1450, "is_me": True},
        {"rank": 2, "name": "Елена В.", "school": "Лицей БГУ г. Минск", "xp": 1390, "is_me": False},
        {"rank": 3, "name": "Максим Т.", "school": "Гимназия №10 г. Минск", "xp": 1310, "is_me": False},
        {"rank": 4, "name": "София К.", "school": "Гимназия №50 г. Минск", "xp": 1240, "is_me": False},
        {"rank": 5, "name": "Илья Д.", "school": "СШ №199 г. Минск", "xp": 1180, "is_me": False},
        {"rank": 6, "name": "Данила П.", "school": "Гимназия №1 г. Минск", "xp": 1120, "is_me": False},
        {"rank": 7, "name": "Виктория Н.", "school": "СШ №42 г. Минск", "xp": 1050, "is_me": False},
        {"rank": 8, "name": "Артём М.", "school": "Гимназия №7 г. Минск", "xp": 990, "is_me": False},
        {"rank": 9, "name": "Дарья О.", "school": "СШ №73 г. Минск", "xp": 940, "is_me": False},
        {"rank": 10, "name": "Никита К.", "school": "Лицей №1 г. Минск", "xp": 890, "is_me": False},
        {"rank": 11, "name": "Анастасия П.", "school": "Гимназия №2 г. Минск", "xp": 850, "is_me": False},
        {"rank": 12, "name": "Вадим Б.", "school": "СШ №121 г. Минск", "xp": 810, "is_me": False},
        {"rank": 13, "name": "Полина Г.", "school": "Гимназия №29 г. Минск", "xp": 770, "is_me": False},
        {"rank": 14, "name": "Роман С.", "school": "СШ №84 г. Минск", "xp": 730, "is_me": False},
        {"rank": 15, "name": "Екатерина И.", "school": "Гимназия №12 г. Минск", "xp": 690, "is_me": False}
    ]
}

# ПОЛНЫЙ КАТАЛОГ КЛАССОВ 1-11 ДЛЯ ЭКРАНА КУРСОВ (ШКОЛЬНАЯ БАЗА)
mock_catalog_grades = {
    "how_it_works": [
        "📚 Все классы 1–11 общего среднего образования РБ",
        "• Программа полностью соответствует учебникам Министерства образования РБ",
        "• Поурочные упражнения, изложения 9 кл и симулятор ЦТ/ЦЭ 11 кл"
    ],
    "items": [
        {
            "id": 1,
            "name": "Русский язык",
            "grades": [
                {"grade": 1, "title": "1 класс", "badge": "Начальная", "available": True, "tasks": 120, "topics": 12, "hint": "Азбука и слоги"},
                {"grade": 2, "title": "2 класс", "badge": "Начальная", "available": True, "tasks": 180, "topics": 15, "hint": "Правила переноса"},
                {"grade": 3, "title": "3 класс", "badge": "Начальная", "available": True, "tasks": 210, "topics": 18, "hint": "Части речи"},
                {"grade": 4, "title": "4 класс", "badge": "Начальная", "available": True, "tasks": 250, "topics": 20, "hint": "Падежи и склонения"},
                {"grade": 5, "title": "5 класс", "badge": "Средняя", "available": True, "tasks": 320, "topics": 24, "hint": "Синтаксис и фонетика"},
                {"grade": 6, "title": "6 класс", "badge": "Средняя", "available": True, "tasks": 380, "topics": 28, "hint": "Морфология и орфография"},
                {"grade": 7, "title": "7 класс", "badge": "Средняя", "available": True, "tasks": 420, "topics": 30, "hint": "Причастия и деепричастия"},
                {"grade": 8, "title": "8 класс", "badge": "Средняя", "available": True, "tasks": 460, "topics": 32, "hint": "Односоставные предложения"},
                {"grade": 9, "title": "9 класс", "badge": "Экзамены", "available": True, "tasks": 510, "topics": 35, "hint": "Изложения и сложные предл."},
                {"grade": 10, "title": "10 класс", "badge": "ЦТ / ЦЭ", "available": True, "tasks": 650, "topics": 40, "hint": "Профильная орфография"},
                {"grade": 11, "title": "11 класс", "badge": "ЦТ / ЦЭ 2026", "available": True, "tasks": 1250, "topics": 50, "hint": "Симулятор ЦТ 100 баллов"}
            ]
        },
        {
            "id": 2,
            "name": "Математика",
            "grades": [
                {"grade": 1, "title": "1 класс", "badge": "Счёт 1-20", "available": True, "tasks": 100, "topics": 10, "hint": "Простые примеры"},
                {"grade": 5, "title": "5 класс", "badge": "Дроби", "available": True, "tasks": 300, "topics": 22, "hint": "Обыкновенные дроби"},
                {"grade": 9, "title": "9 класс", "badge": "Алгебра", "available": True, "tasks": 450, "topics": 30, "hint": "Уравнения и геометрия"},
                {"grade": 11, "title": "11 класс", "badge": "ЦТ / ЦЭ", "available": True, "tasks": 980, "topics": 45, "hint": "Полная подготовка"}
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
    port = 8855
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
            elif '/api/tutor/daily-session/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_daily))
            elif '/api/tutor/stats/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_stats))
            elif '/api/tutor/leaderboard/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_leaderboard_many))
            elif '/api/tutor/tariffs/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_tariffs))
            elif '/api/tutor/family/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_family))
            elif '/knowledge/catalog/' in path or '/catalog/' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(mock_catalog_grades))
            else:
                await route.fulfill(status=200, content_type='application/json', body='{}')

        await page.route('**/api/tutor/**', handle_route)

        tasks = [
            ('1_home', 'home'),
            ('2_courses_grades', 'courses'), # Экран курсов с сеткой плиток классов 1-11
            ('3_practice', 'practice'),
            ('4_stats', 'stats'),
            ('5_rating_many', 'rating'), # Экран рейтинга со множеством участников
            ('6_tariffs', 'tariffs'),
            ('7_family', 'family'),
        ]

        for base_name, route in tasks:
            for theme in ['vibe', 'calm']:
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

                out_file = OUTPUT_DIR / f'ratio_{base_name}_{theme}.png'
                await page.screenshot(path=str(out_file), full_page=True)
                print(f'Captured: {out_file.name}')

        await browser.close()
    httpd.shutdown()

    os.system(f'cp {OUTPUT_DIR}/ratio_*.png {ARTIFACT_DIR}/')
    print('All aspect-ratio screenshots captured and copied to artifacts!')

if __name__ == '__main__':
    asyncio.run(capture())
