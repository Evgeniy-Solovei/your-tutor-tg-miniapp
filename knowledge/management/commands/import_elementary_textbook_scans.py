"""
Импорт цветных страниц-сканов учебников начальной школы (2–4 классы, М.Б. Антипова, bel-shkola).

Создаёт кураторские задания со сканом страницы в хорошем разрешении,
чтобы для 2, 3 и 4 классов в разделе «📖 Учебник» открывались настоящие страницы книги.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
try:
    import fitz
except ImportError:
    fitz = None
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from knowledge.models import Task, TaskOption, TaskSolution, Topic


PDF_SPECS = {
    2: [
        {
            'part': 1,
            'file': 'materials/russian/02_klass/textbooks/Rus_yaz_2kl_ch1_Antipova_bel-shkola_2025.pdf',
            'pdf_offset': 6,  # pdf_index + 1 - 6 = printed page
            'pages': [
                (4, 'Звуки и буквы, алфавит, гласные и согласные'),
                (8, 'Твёрдые и мягкие согласные'),
                (13, 'Твёрдые и мягкие согласные'),
                (16, 'Слоги, ударение и правила переноса слов'),
                (20, 'Слоги, ударение и правила переноса слов'),
                (23, 'Твёрдые и мягкие согласные'),
                (28, 'Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'),
                (31, 'Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'),
                (34, 'Разделительный Ь и Ъ, мягкий знак для мягкости'),
                (42, 'Алфавит и порядок слов'),
                (49, 'Звуки и буквы, алфавит, гласные и согласные'),
                (58, 'Слоги, ударение и правила переноса слов'),
                (64, 'Слоги, ударение и правила переноса слов'),
                (74, 'Твёрдые и мягкие согласные'),
                (80, 'Разделительный Ь и Ъ, мягкий знак для мягкости'),
                (88, 'Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'),
                (95, 'Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'),
                (102, 'Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'),
                (110, 'Парные звонкие и глухие согласные в корне'),
                (120, 'Парные звонкие и глухие согласные в корне'),
            ],
        },
        {
            'part': 2,
            'file': 'materials/russian/02_klass/textbooks/Rus_yaz_2kl_ch2_Antipova_bel-shkola_2025.pdf',
            'pdf_offset': 6,
            'pages': [
                (3, 'Безударные гласные в корне слова и их проверка'),
                (12, 'Безударные гласные в корне слова и их проверка'),
                (22, 'Слово и его значение, синонимы и антонимы'),
                (31, 'Слово и его значение, синонимы и антонимы'),
                (34, 'Слово и его значение, синонимы и антонимы'),
                (37, 'Слова, обозначающие предметы, признаки и действия'),
                (44, 'Слова, обозначающие предметы, признаки и действия'),
                (50, 'Слова, обозначающие предметы, признаки и действия'),
                (57, 'Слова, обозначающие предметы, признаки и действия'),
                (67, 'Предлог'),
                (72, 'Родственные слова и корень слова'),
                (77, 'Родственные слова и корень слова'),
                (90, 'Главные члены: подлежащее и сказуемое'),
                (100, 'Речь устная и письменная, текст и предложение'),
            ],
        },
    ],
    3: [
        {
            'part': 1,
            'file': 'materials/russian/03_klass/textbooks/Rus_yaz_3kl_ch1_Antipova_2023.pdf',
            'pdf_offset': 6,
            'pages': [
                (3, 'Повторение: текст, предложение, главные члены'),
                (7, 'Повторение: текст, предложение, главные члены'),
                (12, 'Повторение: текст, предложение, главные члены'),
                (19, 'Типы текстов'),
                (23, 'Повторение: текст, предложение, главные члены'),
                (26, 'Повторение: текст, предложение, главные члены'),
                (31, 'Повторение: текст, предложение, главные члены'),
                (38, 'Второстепенные члены и однородные члены предложения'),
                (42, 'Второстепенные члены и однородные члены предложения'),
                (56, 'Корень, окончание и основа слова'),
                (60, 'Корень, окончание и основа слова'),
                (68, 'Приставка и суффикс, разбор по составу'),
                (75, 'Приставка и суффикс, разбор по составу'),
                (86, 'Чередование звуков и беглые гласные в корне'),
                (94, 'Безударные гласные и парные согласные в корне'),
                (106, 'Непроизносимые согласные и двойные согласные'),
                (116, 'Непроизносимые согласные и двойные согласные'),
            ],
        },
        {
            'part': 2,
            'file': 'materials/russian/03_klass/textbooks/Rus_yaz_3kl_ch2_Antipova_2023.pdf',
            'pdf_offset': 6,
            'pages': [
                (3, 'Род и число имён существительных'),
                (14, 'Род и число имён существительных'),
                (24, 'Падежи имён существительных (И, Р, Д, В, Т, П)'),
                (34, 'Падежи имён существительных (И, Р, Д, В, Т, П)'),
                (46, 'Мягкий знак после шипящих у существительных'),
                (56, 'Род, число и падежи имён прилагательных'),
                (68, 'Род, число и падежи имён прилагательных'),
                (82, 'Личные местоимения 1, 2, 3 лица'),
                (94, 'Времена глагола и частица НЕ'),
                (108, 'Времена глагола и частица НЕ'),
                (120, 'Итоговое повторение программы 3 класса'),
            ],
        },
    ],
    4: [
        {
            'part': 1,
            'file': 'materials/russian/04_klass/textbooks/Rus_yaz_4kl_ch1_Antipova_2024.pdf',
            'pdf_offset': 6,
            'pages': [
                (3, 'Повторение изученного в 3 классе'),
                (9, 'Состав слова и правописание корней'),
                (12, '1-е склонение и падежные окончания'),
                (23, '1-е склонение и падежные окончания'),
                (35, '2-е склонение и падежные окончания'),
                (46, '3-е склонение и множественное число'),
                (55, '2-е склонение и падежные окончания'),
                (66, '3-е склонение и множественное число'),
                (78, 'Склонение прилагательных мужского и среднего рода'),
                (92, 'Склонение прилагательных женского рода и во мн. числе'),
                (105, 'Склонение прилагательных женского рода и во мн. числе'),
            ],
        },
        {
            'part': 2,
            'file': 'materials/russian/04_klass/textbooks/Rus_yaz_4kl_ch2_Antipova_2024.pdf',
            'pdf_offset': 6,
            'pages': [
                (3, 'Личные местоимения и их склонение'),
                (15, 'Личные местоимения и их склонение'),
                (28, 'Неопределённая форма глагола (инфинитив)'),
                (38, 'Времена глагола и суффикс прошедшего времени'),
                (48, 'I и II спряжение глаголов'),
                (60, 'Определение спряжения по инфинитиву и 11 исключений'),
                (74, 'Правописание -тся/-ться и Ь во 2-м лице'),
                (88, 'Предложение и обращение'),
                (98, 'Однородные члены и сложные предложения'),
                (112, 'Комплексное повторение за курс начальной школы'),
            ],
        },
    ],
}


class Command(BaseCommand):
    help = 'Импортировать цветные страницы-сканы учебников 2–4 классов (Антипова, bel-shkola)'

    def add_arguments(self, parser):
        parser.add_argument('--grade', type=int, default=0, help='Класс (2, 3, 4 или 0 = все 2-4)')

    def handle(self, *args, **options):
        selected_grade = options['grade']
        grades = [selected_grade] if selected_grade in (2, 3, 4) else [2, 3, 4]

        media_root = settings.MEDIA_ROOT
        total_created = 0

        for grade in grades:
            self.stdout.write(self.style.NOTICE(f'=== Обработка учебника {grade} класса ==='))
            topics_qs = list(Topic.objects.filter(grade_level=grade, is_active=True))
            topics_by_name = {t.name.strip().lower(): t for t in topics_qs}
            topic_names = [t.name for t in topics_qs]

            specs = PDF_SPECS.get(grade, [])
            for spec in specs:
                part = spec['part']
                pdf_rel = spec['file']
                pdf_path = Path(settings.BASE_DIR) / pdf_rel
                doc = None
                if pdf_path.exists() and fitz is not None:
                    try:
                        doc = fitz.open(pdf_path)
                    except Exception as e:
                        self.stderr.write(f'Не удалось открыть PDF {pdf_path}: {e}')

                offset = spec['pdf_offset']

                for printed_page, target_topic_name in spec['pages']:
                    img_filename = f'grade{grade}_part{part}_p{printed_page:03d}.png'
                    img_rel = f'tasks/2026/09/{img_filename}'
                    img_full = os.path.join(media_root, img_rel)

                    if not os.path.exists(img_full):
                        if doc is not None:
                            pdf_idx = printed_page + offset - 1
                            if pdf_idx >= len(doc) or pdf_idx < 0:
                                continue
                            page = doc[pdf_idx]
                            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                            os.makedirs(os.path.dirname(img_full), exist_ok=True)
                            pix.save(img_full)
                        else:
                            self.stderr.write(f'Скан {img_rel} не найден на диске и нет PDF, пропускаем')
                            continue

                    # Находим подходящую тему
                    topic = topics_by_name.get(target_topic_name.strip().lower())
                    if not topic:
                        # Попробуем частичное совпадение
                        for t in topics_qs:
                            if target_topic_name.lower() in t.name.lower() or t.name.lower() in target_topic_name.lower():
                                topic = t
                                break
                    if not topic and topics_qs:
                        topic = topics_qs[0]

                    source = f'Учебник «Русский язык» {grade} класс, часть {part}, стр. {printed_page} (М.Б. Антипова, bel-shkola)'

                    # Проверяем, существует ли уже
                    task = Task.objects.filter(source=source).first()
                    is_new = False
                    if not task:
                        is_new = True
                        task = Task(
                            topic=topic,
                            question=(
                                'Посмотри на страницу учебника и задание на ней.\n\n'
                                'К какому разделу русского языка относится этот материал?'
                            ),
                            reading_text='',
                            answer_format=Task.AnswerFormat.SINGLE_CHOICE,
                            scoring_scheme=Task.ScoringScheme.BINARY_1,
                            difficulty=Task.Difficulty.EASY,
                            source=source,
                            is_active=True,
                        )

                    task.image = img_rel
                    task.topic = topic
                    task.save()

                    # Создаем варианты ответов (верный + 3 дистрактора)
                    TaskOption.objects.filter(task=task).delete()
                    distractors = [n for n in topic_names if n != topic.name]
                    import random
                    random.seed(grade * 1000 + part * 100 + printed_page)
                    random.shuffle(distractors)
                    options_list = [topic.name] + distractors[:3]
                    # Перемешаем варианты, но запомним верный
                    shuffled_opts = list(options_list)
                    random.shuffle(shuffled_opts)

                    correct_order = 1
                    for i, opt_text in enumerate(shuffled_opts, start=1):
                        is_corr = (opt_text == topic.name)
                        if is_corr:
                            correct_order = i
                        TaskOption.objects.create(
                            task=task,
                            text=opt_text[:500],
                            is_correct=is_corr,
                            order=i,
                        )

                    TaskSolution.objects.filter(task=task).delete()
                    TaskSolution.objects.create(
                        task=task,
                        correct_answer=str(correct_order),
                        explanation=(
                            f'На странице {printed_page} учебника {grade} класса (часть {part}) '
                            f'изучается тема «{topic.name}». '
                            f'Внимательно рассмотри рисунки, образец и правило на странице учебника.'
                        ),
                    )

                    total_created += 1

                doc.close()
                self.stdout.write(f'  ✓ Часть {part}: обработано {len(spec["pages"])} страниц')

        self.stdout.write(self.style.SUCCESS(
            f'✓ Готово! Всего создано/обновлено {total_created} страниц учебников с цветными сканами!'
        ))
