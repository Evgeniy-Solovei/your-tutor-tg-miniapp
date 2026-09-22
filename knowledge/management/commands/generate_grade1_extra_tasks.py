import os
import math
import random
from PIL import Image, ImageDraw, ImageFont

from django.core.management.base import BaseCommand
from django.conf import settings
from knowledge.models import Topic, TopicExtraTask, Task


# -------------------------------------------------------------
# Drawing Helpers for Kids Flashcards
# -------------------------------------------------------------

def draw_star(draw, cx, cy, r_outer, r_inner, fill):
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=fill)


def draw_bear(draw, cx, cy, size, color=(180, 83, 9)):
    r = size // 2
    ear_r = r // 2
    draw.ellipse([cx - r - ear_r//2, cy - r, cx - r + ear_r*3//2, cy - r + ear_r*2], fill=color)
    draw.ellipse([cx + r - ear_r*3//2, cy - r, cx + r + ear_r//2, cy - r + ear_r*2], fill=color)
    draw.ellipse([cx - r, cy - r + ear_r//2, cx - r + ear_r, cy - r + ear_r*3//2], fill=(254, 215, 170))
    draw.ellipse([cx + r - ear_r, cy - r + ear_r//2, cx + r, cy - r + ear_r*3//2], fill=(254, 215, 170))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    m_w, m_h = r * 4 // 5, r * 3 // 5
    draw.ellipse([cx - m_w//2, cy + r//6, cx + m_w//2, cy + r//6 + m_h], fill=(254, 215, 170))
    draw.ellipse([cx - r//5, cy + r//4, cx + r//5, cy + r//4 + r//4], fill=(30, 20, 10))
    draw.ellipse([cx - r//2, cy - r//6, cx - r//2 + r//4, cy - r//6 + r//4], fill=(30, 20, 10))
    draw.ellipse([cx + r//4, cy - r//6, cx + r//4 + r//4, cy - r//6 + r//4], fill=(30, 20, 10))
    draw.arc([cx - r//4, cy + r//3, cx + r//4, cy + r//2 + r//8], start=20, end=160, fill=(30, 20, 10), width=2)


def draw_fox(draw, cx, cy, size, color=(234, 88, 12)):
    r = size // 2
    draw.polygon([(cx - r, cy), (cx - r - r//4, cy - r*5//4), (cx - r//4, cy - r//2)], fill=color)
    draw.polygon([(cx + r, cy), (cx + r + r//4, cy - r*5//4), (cx + r//4, cy - r//2)], fill=color)
    draw.polygon([(cx - r + 2, cy - 2), (cx - r - r//6, cy - r), (cx - r//3, cy - r//2)], fill=(254, 215, 170))
    draw.polygon([(cx + r - 2, cy - 2), (cx + r + r//6, cy - r), (cx + r//3, cy - r//2)], fill=(254, 215, 170))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    draw.ellipse([cx - r, cy, cx, cy + r], fill=(255, 255, 255))
    draw.ellipse([cx, cy, cx + r, cy + r], fill=(255, 255, 255))
    draw.ellipse([cx - r//5, cy + r//2, cx + r//5, cy + r*3//4], fill=(30, 20, 10))
    draw.ellipse([cx - r//2, cy - r//6, cx - r//4, cy + r//8], fill=(30, 20, 10))
    draw.ellipse([cx + r//4, cy - r//6, cx + r//2, cy + r//8], fill=(30, 20, 10))


def draw_bunny(draw, cx, cy, size, color=(241, 245, 249)):
    r = size // 2
    draw.ellipse([cx - r*2//3, cy - r*7//4, cx - r//6, cy - r//4], fill=color, outline=(203, 213, 225), width=1)
    draw.ellipse([cx + r//6, cy - r*7//4, cx + r*2//3, cy - r//4], fill=color, outline=(203, 213, 225), width=1)
    draw.ellipse([cx - r//2, cy - r*3//2, cx - r//3, cy - r//2], fill=(251, 207, 232))
    draw.ellipse([cx + r//3, cy - r*3//2, cx + r//2, cy - r//2], fill=(251, 207, 232))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=(203, 213, 225), width=1)
    draw.ellipse([cx - r//6, cy + r//8, cx + r//6, cy + r*3//8], fill=(244, 114, 182))
    draw.ellipse([cx - r//2, cy - r//4, cx - r//4, cy], fill=(30, 20, 10))
    draw.ellipse([cx + r//4, cy - r//4, cx + r//2, cy], fill=(30, 20, 10))


def draw_cat(draw, cx, cy, size, color=(251, 146, 60)):
    r = size // 2
    draw.polygon([(cx - r, cy - r//4), (cx - r//2, cy - r*5//4), (cx, cy - r//2)], fill=color)
    draw.polygon([(cx, cy - r//2), (cx + r//2, cy - r*5//4), (cx + r, cy - r//4)], fill=color)
    draw.polygon([(cx - r*4//5, cy - r//4), (cx - r//2, cy - r), (cx - r//5, cy - r//2)], fill=(254, 205, 211))
    draw.polygon([(cx + r//5, cy - r//2), (cx + r//2, cy - r), (cx + r*4//5, cy - r//4)], fill=(254, 205, 211))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    draw.ellipse([cx - r//2, cy - r//6, cx - r//4, cy + r//8], fill=(13, 148, 136))
    draw.ellipse([cx + r//4, cy - r//6, cx + r//2, cy + r//8], fill=(13, 148, 136))
    draw.polygon([(cx - r//8, cy + r//6), (cx + r//8, cy + r//6), (cx, cy + r//3)], fill=(244, 63, 94))
    draw.line([(cx - r*3//4, cy + r//6), (cx - r//4, cy + r//4)], fill=(80, 50, 30), width=1)
    draw.line([(cx + r//4, cy + r//4), (cx + r*3//4, cy + r//6)], fill=(80, 50, 30), width=1)


def draw_frog(draw, cx, cy, size, color=(34, 197, 94)):
    r = size // 2
    draw.ellipse([cx - r*3//4, cy - r*5//4, cx - r//8, cy - r//4], fill=color)
    draw.ellipse([cx + r//8, cy - r*5//4, cx + r*3//4, cy - r//4], fill=color)
    draw.ellipse([cx - r*5//8, cy - r*9//8, cx - r//4, cy - r*3//8], fill='white')
    draw.ellipse([cx + r//4, cy - r*9//8, cx + r*5//8, cy - r*3//8], fill='white')
    draw.ellipse([cx - r//2, cy - r, cx - r//3, cy - r//2], fill=(20, 30, 20))
    draw.ellipse([cx + r//3, cy - r, cx + r//2, cy - r//2], fill=(20, 30, 20))
    draw.ellipse([cx - r*11//10, cy - r*4//5, cx + r*11//10, cy + r], fill=color)
    draw.arc([cx - r*3//5, cy - r//8, cx + r*3//5, cy + r*3//5], start=20, end=160, fill=(20, 80, 30), width=3)


PALETTES = [
    {
        'bg1': (255, 140, 100), 'bg2': (254, 178, 120),
        'accent': (234, 88, 12),
        'pill_bg': (254, 237, 213), 'pill_fg': (194, 65, 12),
        'box_bg': (255, 247, 237), 'box_border': (253, 186, 116),
        'word_fg': (154, 52, 18), 'star': (254, 240, 138),
    },
    {
        'bg1': (244, 114, 182), 'bg2': (251, 191, 36),
        'accent': (219, 39, 119),
        'pill_bg': (252, 231, 243), 'pill_fg': (157, 23, 77),
        'box_bg': (253, 242, 248), 'box_border': (244, 114, 182),
        'word_fg': (131, 24, 67), 'star': (254, 240, 138),
    },
    {
        'bg1': (52, 211, 153), 'bg2': (96, 165, 250),
        'accent': (5, 150, 105),
        'pill_bg': (209, 250, 229), 'pill_fg': (4, 120, 87),
        'box_bg': (236, 253, 245), 'box_border': (110, 231, 183),
        'word_fg': (6, 95, 70), 'star': (254, 240, 138),
    },
    {
        'bg1': (96, 165, 250), 'bg2': (167, 139, 250),
        'accent': (37, 99, 235),
        'pill_bg': (219, 234, 254), 'pill_fg': (29, 78, 216),
        'box_bg': (239, 246, 255), 'box_border': (147, 197, 253),
        'word_fg': (30, 58, 138), 'star': (254, 240, 138),
    },
    {
        'bg1': (192, 132, 252), 'bg2': (244, 114, 182),
        'accent': (126, 34, 206),
        'pill_bg': (243, 232, 255), 'pill_fg': (107, 33, 168),
        'box_bg': (250, 245, 255), 'box_border': (216, 180, 254),
        'word_fg': (88, 28, 135), 'star': (254, 240, 138),
    },
    {
        'bg1': (251, 191, 36), 'bg2': (249, 115, 22),
        'accent': (217, 119, 6),
        'pill_bg': (254, 243, 199), 'pill_fg': (180, 83, 9),
        'box_bg': (255, 251, 235), 'box_border': (252, 211, 77),
        'word_fg': (120, 53, 15), 'star': (255, 255, 255),
    },
]

MASCOT_FUNCS = {
    'bear': draw_bear,
    'fox': draw_fox,
    'bunny': draw_bunny,
    'cat': draw_cat,
    'frog': draw_frog,
}


def render_card_image(file_path, topic_name, focus_word, rule_text, mascot_name, palette_idx=0):
    w, h = 600, 360
    palette = PALETTES[palette_idx % len(PALETTES)]
    img = Image.new('RGB', (w, h), color=palette['bg1'])
    draw = ImageDraw.Draw(img)

    # Gradient background
    c1, c2 = palette['bg1'], palette['bg2']
    for y in range(h):
        t = y / h
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Sparkle stars in corners
    draw_star(draw, 50, 48, 15, 6, fill=palette['star'])
    draw_star(draw, w - 50, 48, 15, 6, fill=palette['star'])
    draw_star(draw, 60, h - 45, 14, 6, fill=palette['star'])
    draw_star(draw, w - 60, h - 45, 14, 6, fill=palette['star'])

    # Inner white card
    draw.rounded_rectangle([22, 22, w - 22, h - 22], radius=24, fill=(255, 255, 255), outline=palette['accent'], width=3)

    # Top header pill
    font_bold = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 15)
    badge_title = f'1 КЛАСС · {topic_name.upper()[:24]}'
    draw.rounded_rectangle([42, 38, 360, 74], radius=18, fill=palette['pill_bg'])
    draw.text((56, 47), badge_title, font=font_bold, fill=palette['pill_fg'])

    # Mascot on top right
    mascot_fn = MASCOT_FUNCS.get(mascot_name, draw_bear)
    mascot_fn(draw, w - 75, 56, 44)

    # Central display box
    draw.rounded_rectangle([42, 92, w - 42, 266], radius=20, fill=palette['box_bg'], outline=palette['box_border'], width=2)

    # Focus word (centered)
    word_len = len(focus_word)
    font_size = 42 if word_len <= 12 else (34 if word_len <= 18 else 26)
    word_font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', font_size)
    bbox = draw.textbbox((0, 0), focus_word, font=word_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) // 2, 118 + (42 - font_size) // 2), focus_word, font=word_font, fill=palette['word_fg'])

    # Rule badge pill
    rule_font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 16)
    rbox = draw.textbbox((0, 0), rule_text, font=rule_font)
    rw = rbox[2] - rbox[0]
    badge_w = min(rw + 32, w - 80)
    badge_x = (w - badge_w) // 2
    draw.rounded_rectangle([badge_x, 196, badge_x + badge_w, 238], radius=14, fill=palette['accent'])
    # Clip rule text if too long
    display_rule = rule_text if rw + 32 <= badge_w else rule_text[:35] + '…'
    rbox2 = draw.textbbox((0, 0), display_rule, font=rule_font)
    rw2 = rbox2[2] - rbox2[0]
    draw.text(((w - rw2) // 2, 206), display_rule, font=rule_font, fill='white')

    # Bottom tip
    tip_font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
    draw.text((46, 298), 'Подсказка: внимательно прочитай задание и выбери верный ответ!', font=tip_font, fill=(100, 116, 139))

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    img.save(file_path, 'PNG')


class Command(BaseCommand):
    help = 'Генерация 50 красочных заданий с картинками на каждую тему для 1 класса'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=== Генерация банка из 50 заданий на тему для 1 класса ==='))

        # Fetch existing textbook tasks to strictly avoid repeating questions
        textbook_questions = set(Task.objects.filter(topic__grade_level=1).values_list('question', flat=True))
        self.stdout.write(f'Найдено {len(textbook_questions)} вопросов из учебника (дубли исключаются)')

        # Grade 1 active topics
        topics = list(Topic.objects.filter(grade_level=1, is_active=True).order_by('id'))
        self.stdout.write(f'Активных тем 1 класса: {len(topics)}')

        from .generators_grade1 import generate_50_tasks_for_topic

        total_created = 0
        media_root = settings.MEDIA_ROOT
        mascots = ['bear', 'fox', 'bunny', 'cat', 'frog']

        for topic_idx, topic in enumerate(topics, 1):
            # Generate 50 unique tasks for this topic
            tasks_data = generate_50_tasks_for_topic(topic.id, topic.name, textbook_questions)
            
            # Remove previous extra tasks for this topic
            TopicExtraTask.objects.filter(topic=topic).delete()

            created_for_topic = 0
            for i, item in enumerate(tasks_data, 1):
                mascot = mascots[(topic.id + i) % len(mascots)]
                palette_idx = (topic.id + i) % len(PALETTES)

                # Generate image
                img_rel_dir = f'extra_tasks/grade1/topic_{topic.id}'
                img_filename = f'task_{i}.png'
                img_full_path = os.path.join(media_root, img_rel_dir, img_filename)
                img_url = f'/media/{img_rel_dir}/{img_filename}'

                render_card_image(
                    file_path=img_full_path,
                    topic_name=topic.name,
                    focus_word=item.get('card_word', topic.name),
                    rule_text=item.get('card_rule', 'Правило 1 класса'),
                    mascot_name=mascot,
                    palette_idx=palette_idx,
                )

                TopicExtraTask.objects.create(
                    topic=topic,
                    question=item['question'],
                    reading_text=item.get('reading_text', ''),
                    image=f'{img_rel_dir}/{img_filename}',
                    image_url=img_url,
                    options=item['options'],
                    correct_answer=item['correct_answer'],
                    explanation=item.get('explanation', ''),
                    difficulty=item.get('difficulty', 'medium'),
                    order=i,
                    source='illustrated_ai_v2',
                    is_active=True,
                )
                created_for_topic += 1
                total_created += 1

            self.stdout.write(f'[{topic_idx}/{len(topics)}] Тема {topic.id} «{topic.name}»: создано {created_for_topic} заданий с картинками')

        self.stdout.write(self.style.SUCCESS(f'✓ Успешно сгенерировано {total_created} заданий с красочными карточками!'))
