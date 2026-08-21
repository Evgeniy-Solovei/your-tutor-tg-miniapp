"""Детские PNG-иллюстрации для заданий 1–4 класса (Pillow)."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont


COLORS = {
    'sky': (186, 230, 253),
    'grass': (134, 239, 172),
    'sun': (253, 224, 71),
    'cat': (251, 146, 60),
    'dog': (180, 140, 100),
    'fish': (56, 189, 248),
    'ball': (248, 113, 113),
    'house': (252, 165, 165),
    'tree': (34, 197, 94),
    'ink': (30, 41, 59),
    'card': (255, 255, 255),
    'accent': (99, 102, 241),
    'pink': (244, 114, 182),
}


def _font(size: int):
    for name in (
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ):
        if Path(name).exists():
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _canvas(w=640, h=420, bg=None):
    bg = bg or COLORS['sky']
    img = Image.new('RGB', (w, h), bg)
    draw = ImageDraw.Draw(img)
    # травка снизу
    draw.rectangle([0, h - 70, w, h], fill=COLORS['grass'])
    return img, draw


def _save(img: Image.Image, name: str) -> Path:
    out_dir = Path(settings.MEDIA_ROOT) / 'tasks' / 'primary'
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{name}.png'
    img.save(path, 'PNG', optimize=True)
    return path


def letter_card(letter: str, subtitle: str = '') -> Path:
    img, draw = _canvas(bg=(255, 247, 237))
    draw.rounded_rectangle([80, 40, 560, 320], radius=40, fill=COLORS['card'], outline=COLORS['accent'], width=6)
    draw.text((320, 150), letter.upper(), font=_font(140), fill=COLORS['accent'], anchor='mm')
    if subtitle:
        draw.text((320, 280), subtitle, font=_font(28), fill=COLORS['ink'], anchor='mm')
    return _save(img, f'letter_{letter.lower()}')


def syllables_mama() -> Path:
    img, draw = _canvas(bg=(254, 243, 199))
    draw.rounded_rectangle([60, 80, 280, 220], radius=28, fill=(254, 249, 195), outline=COLORS['pink'], width=5)
    draw.rounded_rectangle([360, 80, 580, 220], radius=28, fill=(254, 249, 195), outline=COLORS['pink'], width=5)
    draw.text((170, 150), 'МА', font=_font(72), fill=COLORS['pink'], anchor='mm')
    draw.text((470, 150), 'МА', font=_font(72), fill=COLORS['pink'], anchor='mm')
    draw.text((320, 300), 'ма + ма = мама', font=_font(36), fill=COLORS['ink'], anchor='mm')
    return _save(img, 'syllables_mama')


def count_objects(kind: str, n: int) -> Path:
    img, draw = _canvas()
    # солнышко
    draw.ellipse([520, 20, 600, 100], fill=COLORS['sun'])
    positions = [
        (120, 160), (280, 160), (440, 160),
        (200, 260), (360, 260),
    ]
    for i in range(n):
        x, y = positions[i]
        if kind == 'ball':
            draw.ellipse([x - 45, y - 45, x + 45, y + 45], fill=COLORS['ball'], outline=COLORS['ink'], width=3)
        elif kind == 'fish':
            draw.ellipse([x - 50, y - 28, x + 30, y + 28], fill=COLORS['fish'])
            draw.polygon([(x + 28, y), (x + 60, y - 22), (x + 60, y + 22)], fill=COLORS['accent'])
            draw.ellipse([x - 20, y - 8, x - 8, y + 4], fill=COLORS['ink'])
        elif kind == 'apple':
            draw.ellipse([x - 40, y - 40, x + 40, y + 40], fill=(239, 68, 68))
            draw.rectangle([x - 4, y - 55, x + 4, y - 35], fill=(120, 53, 15))
        else:
            draw.ellipse([x - 40, y - 40, x + 40, y + 40], fill=COLORS['cat'])
    draw.text((320, 50), f'Сколько? → {n}', font=_font(32), fill=COLORS['ink'], anchor='mm')
    return _save(img, f'count_{kind}_{n}')


def animal(kind: str) -> Path:
    img, draw = _canvas()
    draw.ellipse([520, 20, 600, 100], fill=COLORS['sun'])
    cx, cy = 320, 200
    if kind == 'cat':
        draw.ellipse([cx - 90, cy - 70, cx + 90, cy + 90], fill=COLORS['cat'])
        draw.polygon([(cx - 70, cy - 40), (cx - 40, cy - 120), (cx - 10, cy - 50)], fill=COLORS['cat'])
        draw.polygon([(cx + 10, cy - 50), (cx + 40, cy - 120), (cx + 70, cy - 40)], fill=COLORS['cat'])
        draw.ellipse([cx - 35, cy - 10, cx - 15, cy + 10], fill=COLORS['ink'])
        draw.ellipse([cx + 15, cy - 10, cx + 35, cy + 10], fill=COLORS['ink'])
        draw.ellipse([cx - 12, cy + 20, cx + 12, cy + 40], fill=(251, 113, 133))
        label = 'кот'
    elif kind == 'dog':
        draw.ellipse([cx - 100, cy - 60, cx + 100, cy + 90], fill=COLORS['dog'])
        draw.ellipse([cx - 120, cy - 20, cx - 70, cy + 40], fill=COLORS['dog'])
        draw.ellipse([cx + 70, cy - 20, cx + 120, cy + 40], fill=COLORS['dog'])
        draw.ellipse([cx - 35, cy - 5, cx - 15, cy + 15], fill=COLORS['ink'])
        draw.ellipse([cx + 15, cy - 5, cx + 35, cy + 15], fill=COLORS['ink'])
        label = 'пёс'
    elif kind == 'fish':
        draw.ellipse([cx - 110, cy - 50, cx + 70, cy + 50], fill=COLORS['fish'])
        draw.polygon([(cx + 65, cy), (cx + 130, cy - 45), (cx + 130, cy + 45)], fill=COLORS['accent'])
        draw.ellipse([cx - 50, cy - 15, cx - 25, cy + 10], fill=COLORS['ink'])
        label = 'рыба'
    else:
        draw.rectangle([cx - 80, cy - 20, cx + 80, cy + 100], fill=COLORS['house'])
        draw.polygon([(cx - 100, cy - 20), (cx, cy - 110), (cx + 100, cy - 20)], fill=(239, 68, 68))
        draw.rectangle([cx - 25, cy + 30, cx + 25, cy + 100], fill=(120, 53, 15))
        label = 'дом'
    draw.rounded_rectangle([200, 330, 440, 390], radius=20, fill=COLORS['card'])
    draw.text((320, 360), label, font=_font(36), fill=COLORS['ink'], anchor='mm')
    return _save(img, f'animal_{kind}')


def word_scheme(word: str, scheme: str) -> Path:
    img, draw = _canvas(bg=(237, 233, 254))
    draw.text((320, 80), word, font=_font(64), fill=COLORS['accent'], anchor='mm')
    draw.text((320, 180), 'схема:', font=_font(28), fill=COLORS['ink'], anchor='mm')
    draw.rounded_rectangle([120, 220, 520, 320], radius=24, fill=COLORS['card'], outline=COLORS['accent'], width=4)
    draw.text((320, 270), scheme, font=_font(48), fill=COLORS['pink'], anchor='mm')
    return _save(img, f'scheme_{word}')


def soft_sign_pair() -> Path:
    img, draw = _canvas(bg=(255, 228, 230))
    draw.rounded_rectangle([40, 60, 300, 280], radius=28, fill=COLORS['card'], outline=COLORS['pink'], width=4)
    draw.rounded_rectangle([340, 60, 600, 280], radius=28, fill=COLORS['card'], outline=COLORS['accent'], width=4)
    draw.text((170, 140), 'уголь', font=_font(44), fill=COLORS['ink'], anchor='mm')
    draw.text((170, 210), 'мягкий знак ь', font=_font(24), fill=COLORS['pink'], anchor='mm')
    draw.text((470, 140), 'угол', font=_font(44), fill=COLORS['ink'], anchor='mm')
    draw.text((470, 210), 'без ь', font=_font(24), fill=COLORS['accent'], anchor='mm')
    draw.text((320, 340), 'ь смягчает согласный', font=_font(28), fill=COLORS['ink'], anchor='mm')
    return _save(img, 'soft_sign')


def root_words() -> Path:
    img, draw = _canvas(bg=(220, 252, 231))
    for i, (word, x) in enumerate([('лес', 140), ('лесной', 320), ('лесок', 500)]):
        draw.rounded_rectangle([x - 70, 120, x + 70, 220], radius=20, fill=COLORS['card'], outline=COLORS['tree'], width=4)
        draw.text((x, 170), word, font=_font(32), fill=COLORS['ink'], anchor='mm')
    draw.text((320, 280), 'общий корень: лес', font=_font(34), fill=COLORS['tree'], anchor='mm')
    return _save(img, 'root_les')


def sentence_capitals() -> Path:
    img, draw = _canvas(bg=(224, 242, 254))
    draw.rounded_rectangle([60, 100, 580, 260], radius=28, fill=COLORS['card'], outline=COLORS['accent'], width=5)
    draw.text((320, 160), 'маша читает книгу', font=_font(36), fill=(148, 163, 184), anchor='mm')
    draw.text((320, 220), 'Маша читает книгу.', font=_font(36), fill=COLORS['ink'], anchor='mm')
    draw.text((320, 320), 'Имя — с заглавной + точка', font=_font(28), fill=COLORS['accent'], anchor='mm')
    return _save(img, 'sentence_capital')
