"""
Модуль отрисовки красочных детских карточек в стилистике любимых франшиз:
- Roblox (Роблокс)
- Toca Boca (Тока Бока)
- Маша и Медведь
- Minecraft (Майнкрафт)
- Brawl Stars (Бравл Старс)

ГЛАВНОЕ ПРАВИЛО: Карточка НИКОГДА не показывает правильный ответ!
Она иллюстрирует задание, мотивирует ребёнка через любимых героев и показывает
слово с пропусками или карточку-загадку [ ? ].
"""

import os
import re
from PIL import Image, ImageDraw, ImageFont


def get_font(size: int, bold: bool = True):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundled_bold = os.path.join(base_dir, 'fonts', 'Arial-Bold.ttf')
    bundled_regular = os.path.join(base_dir, 'fonts', 'Arial.ttf')

    candidates = [
        bundled_bold if bold else bundled_regular,
        '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def extract_safe_display_prompt(question: str, correct_answer: str, topic_name: str) -> tuple[str, str]:
    """
    Извлекает безопасный текст для карточки без спойлера ответа.
    Возвращает (prompt_text, sub_hint).
    """
    correct_clean = str(correct_answer).strip().lower()

    # 1. Ищем шаблон с пропусками в кавычках («...», "...", '...')
    m = re.search(r'[«"\'`]([^»"\'`]+)[»"\'`]', question or '')
    if m:
        candidate = m.group(1).strip()
        # Если кандидат это и есть правильный ответ (спойлер!) — скрываем его!
        if candidate.lower() == correct_clean or correct_clean in candidate.lower() and len(correct_clean) > 2 and '...' not in candidate:
            return "ЗАГАДКА [ ? ]", "Внимательно выбери правильный ответ внизу!"
        # Если в слове есть пропуски (... или .. или _), показываем его красиво с пробелами
        if '...' in candidate or '..' in candidate or '_' in candidate:
            spaced = candidate.replace('...', ' . . . ').replace('..', ' . . ').replace('_', ' _ ')
            spaced = re.sub(r'\s+', ' ', spaced).strip().upper()
            return spaced, "Какая буква пропущена? Подумай!"
        # Если это просто слово из вопроса, в котором ищут правило
        return candidate.upper()[:24], "Внимательно прочитай вопрос задания!"

    # 2. Если вопрос про алфавит («первая буква», «последняя буква», «после буквы»)
    q_lower = (question or '').lower()
    if 'алфавит' in q_lower or 'азбук' in q_lower:
        if 'перв' in q_lower:
            return "АЛФАВИТ · СТАРТ [ ? ]", "С какой буквы начинается русский алфавит?"
        elif 'последн' in q_lower:
            return "АЛФАВИТ · ФИНИШ [ ? ]", "Какая буква завершает алфавит?"
        elif 'после' in q_lower:
            m_let = re.search(r'буквы\s+[«"\'`]?([а-яёА-ЯЁ])[»"\'`]?', question)
            if m_let:
                return f"БУКВА {m_let.group(1).upper()} ➔ [ ? ]", "Какая буква идёт следующей по порядку?"
            return "ПОРЯДОК БУКВ [ ? ]", "Вспомни правильный порядок в алфавите!"
        return "РУССКИЙ АЛФАВИТ", "33 буквы от А до Я!"

    # 3. Если вопрос про звуки, слоги или части речи
    if 'слог' in q_lower:
        return "СЛОГИ И УДАРЕНИЕ", "Раздели слово на части и найди верный ответ!"
    if 'гласн' in q_lower or 'согласн' in q_lower:
        return "ЗВУКИ И БУКВЫ", "Гласный или согласный? Выбери внизу!"
    if 'существительн' in q_lower or 'глагол' in q_lower or 'прилагательн' in q_lower:
        return "ЧАСТИ РЕЧИ", "Определи роль слова в предложении!"

    # 4. По умолчанию: тема с challenge бейджем
    clean_topic = topic_name.replace('·', '').strip().upper()[:26]
    return clean_topic or "ИСПЫТАНИЕ [ ? ]", "Прочитай условие и выбери правильный ответ!"


def render_roblox_card(draw, w, h, topic_name, prompt_text, sub_hint, grade):
    # Фоновая сетка
    for x in range(0, w, 32):
        draw.line([(x, 0), (x, h)], fill=(30, 41, 59), width=1)
    for y in range(0, h, 32):
        draw.line([(0, y), (w, y)], fill=(30, 41, 59), width=1)

    # Рамка карточки
    draw.rounded_rectangle([18, 18, w-18, h-18], radius=24, fill=(15, 23, 42), outline=(14, 165, 233), width=3)

    # Хэдер
    f_title = get_font(17, True)
    draw.rounded_rectangle([34, 30, 310, 68], radius=16, fill=(14, 165, 233))
    draw.text((46, 40), f'🎮 ROBLOX · {grade} КЛАСС', font=f_title, fill=(255, 255, 255))

    # Бейдж XP
    f_badge = get_font(13, True)
    draw.rounded_rectangle([w - 170, 30, w - 34, 68], radius=16, fill=(30, 41, 59), outline=(56, 189, 248), width=2)
    draw.text((w - 156, 42), '⭐ +15 XP', font=f_badge, fill=(253, 224, 71))

    # Roblox аватар
    ax, ay = 520, 115
    # Голова
    draw.rounded_rectangle([ax-35, ay-35, ax+35, ay+35], radius=12, fill=(253, 224, 71), outline=(202, 138, 4), width=2)
    # Наушники
    draw.rounded_rectangle([ax-44, ay-15, ax-34, ay+15], radius=6, fill=(14, 165, 233))
    draw.rounded_rectangle([ax+34, ay-15, ax+44, ay+15], radius=6, fill=(14, 165, 233))
    draw.arc([ax-40, ay-45, ax+40, ay], start=180, end=0, fill=(14, 165, 233), width=5)
    # Лицо
    draw.ellipse([ax-18, ay-8, ax-8, ay+2], fill=(15, 23, 42))
    draw.ellipse([ax+8, ay-8, ax+18, ay+2], fill=(15, 23, 42))
    draw.arc([ax-12, ay+4, ax+12, ay+18], start=20, end=160, fill=(15, 23, 42), width=3)
    # Торс
    draw.rounded_rectangle([ax-30, ay+38, ax+30, ay+88], radius=8, fill=(30, 41, 59), outline=(14, 165, 233), width=2)

    # Речевой пузырь
    draw.rounded_rectangle([44, 90, 440, 162], radius=18, fill=(30, 41, 59), outline=(56, 189, 248), width=2)
    draw.polygon([(440, 115), (475, 115), (440, 130)], fill=(30, 41, 59))
    draw.line([(440, 115), (475, 115)], fill=(56, 189, 248), width=2)
    draw.line([(475, 115), (440, 130)], fill=(56, 189, 248), width=2)

    f_bubble = get_font(15, True)
    f_sub = get_font(13, False)
    draw.text((60, 104), '🔥 Помоги пройти Obby-испытание!', font=f_bubble, fill=(253, 224, 71))
    draw.text((60, 130), sub_hint[:45], font=f_sub, fill=(226, 232, 240))

    # Центральное поле испытания (БЕЗ СПОЙЛЕРА!)
    draw.rounded_rectangle([44, 185, w-44, 310], radius=20, fill=(2, 6, 23), outline=(56, 189, 248), width=2)
    f_prompt = get_font(34 if len(prompt_text) <= 14 else (26 if len(prompt_text) <= 22 else 20), True)
    bbox = draw.textbbox((0, 0), prompt_text, font=f_prompt)
    pw = bbox[2] - bbox[0]
    draw.text(((w - pw) // 2, 220), prompt_text, font=f_prompt, fill=(56, 189, 248))
    f_bottom = get_font(13, False)
    draw.text((60, 275), '🎯 Выбери правильный вариант ответа внизу!', font=f_bottom, fill=(148, 163, 184))


def render_toca_boca_card(draw, w, h, topic_name, prompt_text, sub_hint, grade):
    # Пастельный фон
    draw.ellipse([-50, -50, 260, 260], fill=(254, 215, 170))
    draw.ellipse([430, 160, 750, 480], fill=(252, 231, 243))
    draw.rounded_rectangle([18, 18, w-18, h-18], radius=28, fill=(255, 255, 255), outline=(244, 114, 182), width=4)

    # Хэдер
    f_title = get_font(17, True)
    draw.rounded_rectangle([34, 30, 310, 68], radius=20, fill=(244, 114, 182))
    draw.text((46, 40), f'🌈 TOCA LIFE · {grade} КЛАСС', font=f_title, fill=(255, 255, 255))

    # Бейдж
    f_badge = get_font(13, True)
    draw.rounded_rectangle([w - 170, 30, w - 34, 68], radius=18, fill=(254, 242, 242), outline=(244, 114, 182), width=2)
    draw.text((w - 156, 42), '✨ ЗНАНИЯ', font=f_badge, fill=(219, 39, 119))

    # Toca персонаж
    cx, cy = 520, 118
    # Хвостики
    draw.ellipse([cx-40, cy-48, cx-12, cy-20], fill=(236, 72, 153))
    draw.ellipse([cx+12, cy-48, cx+40, cy-20], fill=(236, 72, 153))
    # Голова
    draw.ellipse([cx-32, cy-32, cx+32, cy+32], fill=(254, 226, 226))
    # Чёлка
    draw.arc([cx-32, cy-32, cx+32, cy+10], start=180, end=0, fill=(236, 72, 153), width=14)
    # Румянец
    draw.ellipse([cx-24, cy+4, cx-12, cy+14], fill=(251, 164, 178))
    draw.ellipse([cx+12, cy+4, cx+24, cy+14], fill=(251, 164, 178))
    # Глазки
    draw.ellipse([cx-18, cy-8, cx-10, cy], fill=(30, 20, 30))
    draw.ellipse([cx+10, cy-8, cx+18, cy], fill=(30, 20, 30))
    draw.ellipse([cx-15, cy-8, cx-12, cy-5], fill=(255, 255, 255))
    draw.ellipse([cx+13, cy-8, cx+16, cy-5], fill=(255, 255, 255))
    # Улыбка
    draw.arc([cx-8, cy+2, cx+8, cy+14], start=10, end=170, fill=(30, 20, 30), width=2)
    # Свитер
    draw.rounded_rectangle([cx-24, cy+35, cx+24, cy+85], radius=12, fill=(94, 234, 212))

    # Пузырь
    draw.rounded_rectangle([44, 90, 440, 162], radius=20, fill=(254, 242, 242), outline=(244, 114, 182), width=2)
    draw.polygon([(440, 115), (475, 115), (440, 130)], fill=(254, 242, 242))
    draw.line([(440, 115), (475, 115)], fill=(244, 114, 182), width=2)
    draw.line([(475, 115), (440, 130)], fill=(244, 114, 182), width=2)

    f_bubble = get_font(15, True)
    f_sub = get_font(13, False)
    draw.text((60, 104), '✨ Ура, новая загадка!', font=f_bubble, fill=(219, 39, 119))
    draw.text((60, 130), sub_hint[:45], font=f_sub, fill=(157, 23, 77))

    # Испытание
    draw.rounded_rectangle([44, 185, w-44, 310], radius=22, fill=(255, 241, 242), outline=(251, 113, 133), width=2)
    f_prompt = get_font(34 if len(prompt_text) <= 14 else (26 if len(prompt_text) <= 22 else 20), True)
    bbox = draw.textbbox((0, 0), prompt_text, font=f_prompt)
    pw = bbox[2] - bbox[0]
    draw.text(((w - pw) // 2, 220), prompt_text, font=f_prompt, fill=(190, 24, 93))
    f_bottom = get_font(13, False)
    draw.text((60, 275), '💡 Подсказка: подумай и выбери верную карточку!', font=f_bottom, fill=(159, 18, 57))


def render_masha_card(draw, w, h, topic_name, prompt_text, sub_hint, grade):
    draw.rounded_rectangle([18, 18, w-18, h-18], radius=26, fill=(255, 255, 255), outline=(225, 29, 72), width=4)

    # Хэдер
    f_title = get_font(17, True)
    draw.rounded_rectangle([34, 30, 330, 68], radius=18, fill=(225, 29, 72))
    draw.text((46, 40), f'🐻 МАША И МЕДВЕДЬ · {grade} КЛ.', font=f_title, fill=(255, 255, 255))

    # Бейдж
    f_badge = get_font(13, True)
    draw.rounded_rectangle([w - 170, 30, w - 34, 68], radius=18, fill=(254, 249, 195), outline=(234, 179, 8), width=2)
    draw.text((w - 156, 42), '🍯 УРОК', font=f_badge, fill=(180, 83, 9))

    # Маша
    mx, my = 520, 118
    # Платочек
    draw.ellipse([mx-38, my-40, mx+38, my+36], fill=(244, 63, 94))
    draw.polygon([(mx-38, my+10), (mx, my+60), (mx+38, my+10)], fill=(244, 63, 94))
    # Лицо
    draw.ellipse([mx-26, my-22, mx+26, my+26], fill=(254, 226, 226))
    # Чёлочка
    draw.arc([mx-22, my-24, mx+22, my-5], start=180, end=0, fill=(250, 204, 21), width=10)
    # Зелёные глазки
    draw.ellipse([mx-16, my-6, mx-6, my+4], fill=(22, 163, 74))
    draw.ellipse([mx+6, my-6, mx+16, my+4], fill=(22, 163, 74))
    draw.ellipse([mx-13, my-6, mx-9, my-2], fill=(255, 255, 255))
    draw.ellipse([mx+9, my-6, mx+13, my-2], fill=(255, 255, 255))
    # Улыбка
    draw.arc([mx-10, my+4, mx+10, my+18], start=10, end=170, fill=(190, 18, 60), width=3)
    # Сарафан
    draw.polygon([(mx-25, my+38), (mx+25, my+38), (mx+35, my+85), (mx-35, my+85)], fill=(225, 29, 72))

    # Пузырь
    draw.rounded_rectangle([44, 90, 440, 162], radius=18, fill=(255, 241, 242), outline=(225, 29, 72), width=2)
    draw.polygon([(440, 115), (475, 115), (440, 130)], fill=(255, 241, 242))
    draw.line([(440, 115), (475, 115)], fill=(225, 29, 72), width=2)
    draw.line([(475, 115), (440, 130)], fill=(225, 29, 72), width=2)

    f_bubble = get_font(15, True)
    f_sub = get_font(13, False)
    draw.text((60, 104), '🍯 Мишка, я знаю правило!', font=f_bubble, fill=(159, 18, 57))
    draw.text((60, 130), sub_hint[:45], font=f_sub, fill=(190, 24, 93))

    # Испытание
    draw.rounded_rectangle([44, 185, w-44, 310], radius=20, fill=(254, 249, 195), outline=(234, 179, 8), width=2)
    f_prompt = get_font(34 if len(prompt_text) <= 14 else (26 if len(prompt_text) <= 22 else 20), True)
    bbox = draw.textbbox((0, 0), prompt_text, font=f_prompt)
    pw = bbox[2] - bbox[0]
    draw.text(((w - pw) // 2, 220), prompt_text, font=f_prompt, fill=(180, 83, 9))
    f_bottom = get_font(13, False)
    draw.text((60, 275), '🍓 Лесная школа: не спеши, проверь все варианты!', font=f_bottom, fill=(161, 98, 7))


def render_minecraft_card(draw, w, h, topic_name, prompt_text, sub_hint, grade):
    # Пиксельный фон
    for x in range(0, w, 24):
        for y in range(0, h, 24):
            if (x//24 + y//24) % 2 == 0:
                draw.rectangle([x, y, x+24, y+24], fill=(20, 30, 45))
    draw.rounded_rectangle([18, 18, w-18, h-18], radius=16, fill=(15, 23, 42), outline=(34, 197, 94), width=4)

    # Хэдер
    f_title = get_font(17, True)
    draw.rounded_rectangle([34, 30, 320, 68], radius=12, fill=(34, 197, 94))
    draw.text((46, 40), f'⛏️ MINECRAFT · {grade} КЛАСС', font=f_title, fill=(255, 255, 255))

    # Бейдж
    f_badge = get_font(13, True)
    draw.rounded_rectangle([w - 170, 30, w - 34, 68], radius=12, fill=(30, 41, 59), outline=(34, 197, 94), width=2)
    draw.text((w - 156, 42), '💎 КРАФТ', font=f_badge, fill=(52, 211, 153))

    # Стив
    sx, sy = 520, 118
    draw.rectangle([sx-32, sy-32, sx+32, sy+32], fill=(234, 179, 8), outline=(161, 98, 7), width=2)
    draw.rectangle([sx-32, sy-32, sx+32, sy-14], fill=(68, 40, 20))
    draw.rectangle([sx-22, sy-6, sx-8, sy+2], fill=(255, 255, 255))
    draw.rectangle([sx-14, sy-6, sx-8, sy+2], fill=(37, 99, 235))
    draw.rectangle([sx+8, sy-6, sx+22, sy+2], fill=(255, 255, 255))
    draw.rectangle([sx+16, sy-6, sx+22, sy+2], fill=(37, 99, 235))
    draw.rectangle([sx-6, sy+4, sx+6, sy+12], fill=(180, 120, 60))
    draw.rectangle([sx-12, sy+16, sx+12, sy+24], fill=(68, 40, 20))
    draw.rectangle([sx-30, sy+36, sx+30, sy+85], fill=(6, 182, 212))

    # Пузырь
    draw.rounded_rectangle([44, 90, 440, 162], radius=14, fill=(30, 41, 59), outline=(34, 197, 94), width=2)
    draw.polygon([(440, 115), (475, 115), (440, 130)], fill=(30, 41, 59))
    draw.line([(440, 115), (475, 115)], fill=(34, 197, 94), width=2)
    draw.line([(475, 115), (440, 130)], fill=(34, 197, 94), width=2)

    f_bubble = get_font(15, True)
    f_sub = get_font(13, False)
    draw.text((60, 104), '💎 Скрафти верный ответ!', font=f_bubble, fill=(52, 211, 153))
    draw.text((60, 130), sub_hint[:45], font=f_sub, fill=(203, 213, 225))

    # Испытание
    draw.rectangle([44, 185, w-44, 310], fill=(2, 6, 23), outline=(6, 182, 212), width=3)
    f_prompt = get_font(34 if len(prompt_text) <= 14 else (26 if len(prompt_text) <= 22 else 20), True)
    bbox = draw.textbbox((0, 0), prompt_text, font=f_prompt)
    pw = bbox[2] - bbox[0]
    draw.text(((w - pw) // 2, 220), prompt_text, font=f_prompt, fill=(6, 182, 212))
    f_bottom = get_font(13, False)
    draw.text((60, 275), '⚡ Алмазный сундук ждёт правильного решения!', font=f_bottom, fill=(148, 163, 184))


def render_brawl_stars_card(draw, w, h, topic_name, prompt_text, sub_hint, grade):
    draw.rounded_rectangle([18, 18, w-18, h-18], radius=24, fill=(49, 10, 100), outline=(249, 115, 22), width=4)

    # Хэдер
    f_title = get_font(17, True)
    draw.rounded_rectangle([34, 30, 310, 68], radius=16, fill=(249, 115, 22))
    draw.text((46, 40), f'⚡ BRAWL · {grade} КЛАСС', font=f_title, fill=(255, 255, 255))

    # Бейдж
    f_badge = get_font(13, True)
    draw.rounded_rectangle([w - 170, 30, w - 34, 68], radius=16, fill=(88, 28, 135), outline=(249, 115, 22), width=2)
    draw.text((w - 156, 42), '🏆 БОЕЦ', font=f_badge, fill=(251, 191, 36))

    # Бравлер
    bx, by = 520, 118
    draw.ellipse([bx-32, by-32, bx+32, by+32], fill=(254, 215, 170))
    draw.polygon([(bx-34, by-15), (bx+34, by-15), (bx+30, by-34), (bx-30, by-34)], fill=(239, 68, 68))
    draw.ellipse([bx-42, by-18, bx-30, by-6], fill=(239, 68, 68))
    draw.rounded_rectangle([bx-24, by-8, bx-4, by+8], radius=4, fill=(15, 23, 42), outline=(250, 204, 21), width=2)
    draw.rounded_rectangle([bx+4, by-8, bx+24, by+8], radius=4, fill=(15, 23, 42), outline=(250, 204, 21), width=2)
    draw.line([(bx-4, by), (bx+4, by)], fill=(250, 204, 21), width=2)
    draw.arc([bx-12, by+10, bx+12, by+24], start=10, end=170, fill=(15, 23, 42), width=3)
    draw.rounded_rectangle([bx-26, by+35, bx+26, by+85], radius=10, fill=(249, 115, 22))

    # Пузырь
    draw.rounded_rectangle([44, 90, 440, 162], radius=18, fill=(30, 10, 60), outline=(249, 115, 22), width=2)
    draw.polygon([(440, 115), (475, 115), (440, 130)], fill=(30, 10, 60))
    draw.line([(440, 115), (475, 115)], fill=(249, 115, 22), width=2)
    draw.line([(475, 115), (440, 130)], fill=(249, 115, 22), width=2)

    f_bubble = get_font(15, True)
    f_sub = get_font(13, False)
    draw.text((60, 104), '🔥 Заряжай ульту знаниями!', font=f_bubble, fill=(251, 191, 36))
    draw.text((60, 130), sub_hint[:45], font=f_sub, fill=(253, 224, 71))

    # Испытание
    draw.rounded_rectangle([44, 185, w-44, 310], radius=20, fill=(20, 5, 40), outline=(234, 179, 8), width=3)
    f_prompt = get_font(34 if len(prompt_text) <= 14 else (26 if len(prompt_text) <= 22 else 20), True)
    bbox = draw.textbbox((0, 0), prompt_text, font=f_prompt)
    pw = bbox[2] - bbox[0]
    draw.text(((w - pw) // 2, 220), prompt_text, font=f_prompt, fill=(250, 204, 21))
    f_bottom = get_font(13, False)
    draw.text((60, 275), '🏆 Звёздный трофей: выбери правильный ответ!', font=f_bottom, fill=(245, 158, 11))


STYLES = [
    ('roblox', (15, 23, 42), render_roblox_card),
    ('toca_boca', (254, 243, 199), render_toca_boca_card),
    ('masha', (254, 240, 138), render_masha_card),
    ('minecraft', (30, 41, 59), render_minecraft_card),
    ('brawl_stars', (88, 28, 135), render_brawl_stars_card),
]


def render_kid_cartoon_card(
    file_path: str,
    topic_name: str,
    question_text: str,
    correct_answer: str,
    style_idx: int = 0,
    grade: int = 1,
) -> str:
    """
    Рендерит карточку задания в одной из мультяшных стилистик.
    НИКОГДА не показывает правильный ответ!
    """
    prompt_text, sub_hint = extract_safe_display_prompt(question_text, correct_answer, topic_name)

    style_name, bg_color, render_fn = STYLES[style_idx % len(STYLES)]

    w, h = 640, 380
    img = Image.new('RGB', (w, h), bg_color)
    draw = ImageDraw.Draw(img)

    render_fn(draw, w, h, topic_name, prompt_text, sub_hint, grade)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    img.save(file_path, 'PNG')
    return style_name
