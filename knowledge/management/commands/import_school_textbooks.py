"""
Импорт школьных учебников 1–11 в Task.

1 класс (Антипова, bel-shkola, 2024) — скан с картинками: в БД страница
учебника (image) + текст слоя + раздел из оглавления.

2–11 классы — текстовый слой PDF: полное условие упражнения, без фейковых
вариантов «задание выполнено верно». Старые обёртки отключаются.

  ./venv/bin/python manage.py import_school_textbooks --grade 1
  ./venv/bin/python manage.py import_school_textbooks --grade 2
  ./venv/bin/python manage.py import_school_textbooks --grade 1-11
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import (
    ContentVersion,
    ExamTrack,
    Section,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    Topic,
    TopicSummary,
)

BASE = Path('materials/russian')

# PDF-страница = печатный номер + 2 (обложка + титул).
G1_PDF_OFFSET = 2
G1_PDF = BASE / '01_klass/textbooks/Rus_yaz_1kl_Antipova_bel-shkola_2024.pdf'
G1_SOURCE_PREFIX = 'Учебник «Русский язык» 1 класс, стр.'
G1_AUTHOR = 'М.Б. Антипова, Е.С. Грабчикова, 2024, bel-shkola'

# печатная стр. старта раздела
G1_TOC: list[tuple[int, str]] = [
    (4, 'Наша родина — Беларусь. Мы изучаем русский язык'),
    (10, 'Знакомство'),
    (13, 'Осень школьная пришла'),
    (16, 'Давайте дружить!'),
    (18, 'Моя семья'),
    (24, 'Учимся вежливости'),
    (31, 'Праздник чудный — Новый год!'),
    (36, 'Что такое хорошо и что такое плохо?'),
    (40, 'Солнце, воздух и вода — наши лучшие друзья'),
    (47, 'Добро не умрёт, а зло пропадёт'),
    (50, 'Мамин день'),
    (52, 'Без труда не выловишь и рыбку из пруда'),
    (55, 'Кем быть?'),
    (58, 'В слова играем, друг друга понимаем'),
    (62, 'Сказка — в жизни подсказка'),
    (64, 'Наши домашние любимцы'),
    (67, 'Земное чудо — лес'),
    (70, 'С любовью к природе'),
    (74, 'Учимся видеть прекрасное'),
    (83, 'День за днём'),
]

TEXTBOOKS = {
    2: [
        {
            'pdf': BASE / '02_klass/textbooks/Rus_yaz_2kl_ch1_Guleckaya_rus-shkola_2022.pdf',
            'part': 1,
            'max_num': 221,
            'author': 'А.В. Гулецкая, Е.А. Федорович, 2022',
        },
        {
            'pdf': BASE / '02_klass/textbooks/Rus_yaz_2kl_ch2_Guleckaya_rus-shkola_2022.pdf',
            'part': 2,
            'max_num': 182,
            'author': 'А.В. Гулецкая, Е.А. Федорович, 2022',
        },
        {
            'pdf': BASE / '02_klass/textbooks/Rus_yaz_2kl_ch1_Antipova_bel-shkola_2025.pdf',
            'part': 1,
            'max_num': 220,
            'author': 'М.Б. Антипова, 2025, bel-shkola',
        },
        {
            'pdf': BASE / '02_klass/textbooks/Rus_yaz_2kl_ch2_Antipova_bel-shkola_2025.pdf',
            'part': 2,
            'max_num': 220,
            'author': 'М.Б. Антипова, 2025, bel-shkola',
        },
    ],
    3: [
        {
            'pdf': BASE / '03_klass/textbooks/Rus_yaz_3kl_ch1_Antipova_2023.pdf',
            'part': 1,
            'max_num': 250,
            'author': 'М.Б. Антипова, К.С. Верниковская, 2023',
        },
        {
            'pdf': BASE / '03_klass/textbooks/Rus_yaz_3kl_ch2_Antipova_2023.pdf',
            'part': 2,
            'max_num': 240,
            'author': 'М.Б. Антипова, К.С. Верниковская, 2023',
        },
    ],
    4: [
        {
            'pdf': BASE / '04_klass/textbooks/Rus_yaz_4kl_ch1_Antipova_2024.pdf',
            'part': 1,
            'max_num': 230,
            'author': 'М.Б. Антипова, К.С. Верниковская, 2024',
        },
        {
            'pdf': BASE / '04_klass/textbooks/Rus_yaz_4kl_ch2_Antipova_2024.pdf',
            'part': 2,
            'max_num': 230,
            'author': 'М.Б. Антипова, К.С. Верниковская, 2024',
        },
    ],
    5: [
        {
            'pdf': BASE / '05_klass/textbooks/Rus_yaz_5kl_ch1_Murina_2025.pdf',
            'part': 1,
            'max_num': 280,
            'author': 'Л.А. Мурина, Ф.М. Литвинко, 2025',
        },
        {
            'pdf': BASE / '05_klass/textbooks/Rus_yaz_5kl_ch2_Murina_2025.pdf',
            'part': 2,
            'max_num': 280,
            'author': 'Л.А. Мурина, Ф.М. Литвинко, 2025',
        },
    ],
    6: [
        {
            'pdf': BASE / '06_klass/textbooks/Rus_yaz_6kl_Murina_2020.pdf',
            'part': 0,
            'max_num': 560,
            'author': 'Л.А. Мурина, Ф.М. Литвинко, Е.Е. Долбик, 2020',
        },
    ],
    7: [
        {
            'pdf': BASE / '07_klass/textbooks/Rus_yaz_7kl_Volinec_2020.pdf',
            'part': 0,
            'max_num': 500,
            'author': 'Т.Н. Волынец, Ф.М. Литвинко, 2020',
        },
    ],
    8: [
        {
            'pdf': BASE / '08_klass/textbooks/Rus_yaz_8kl_Murina_2024.pdf',
            'part': 0,
            'max_num': 430,
            'author': 'Л.А. Мурина, Ф.М. Литвинко, 2024',
        },
    ],
    9: [
        {
            'pdf': BASE / '09_klass/textbooks/Rus_yaz_9kl_Murina_2025.pdf',
            'part': 0,
            'max_num': 420,
            'author': 'Л.А. Мурина, Ф.М. Литвинко, 2025',
        },
    ],
    10: [
        {
            'pdf': BASE / '10_klass/textbooks/Rus_yaz_10kl_Leonovich_2020.pdf',
            'part': 0,
            'max_num': 500,
            'author': 'В.Л. Леонович, Л.А. Мурина, 2020',
        },
    ],
    11: [
        {
            'pdf': BASE / '11_klass/textbooks/Rus_yaz_11kl_Dolbik_2021.pdf',
            'part': 0,
            'max_num': 450,
            'author': 'Е.Е. Долбик, 2021',
            'numbering': 'decimal',
        },
    ],
}


FAKE_OPTION_PREFIXES = (
    'Задание выполнено верно',
    'Все пропущенные буквы вставлены строго по правилам',
)


def g1_chapter(printed: int) -> str:
    name = G1_TOC[0][1]
    for start, title in G1_TOC:
        if printed >= start:
            name = title
        else:
            break
    return name


def decode_uni(text: str) -> str:
    return re.sub(r'/uni([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), text)


def clean_page_text(text: str) -> str:
    text = decode_uni(text or '')
    text = re.sub(r'Правообладатель Акадэмія адукацыі\s*', '', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_exercises(pdf_path: Path, max_num: int, numbering: str = 'int') -> dict[str, str]:
    doc = fitz.open(pdf_path)
    parts = []
    for page in doc:
        parts.append(decode_uni(page.get_text() or ''))
    doc.close()
    full_text = '\n'.join(parts)
    cleaned = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', full_text)
    ex_dict: dict[str, str] = {}
    if numbering == 'decimal':
        blocks = re.findall(
            r'(?:^|\n)\s*(\d{1,2}\.\d{1,2})\.\s+([\s\S]*?)(?=(?:\n\s*\d{1,2}\.\d{1,2}\.|\Z))',
            cleaned,
        )
        for s_num, body in blocks:
            body_clean = re.sub(r'\s+', ' ', body.strip())
            if len(body_clean) < 20:
                continue
            ex_dict[s_num] = body_clean
        return ex_dict
    blocks = re.findall(
        r'(?:^|\n)\s*(\d{1,3})\.\s+([\s\S]*?)(?=(?:\n\s*\d{1,3}\.|\Z))',
        cleaned,
    )
    last = 0
    for s_num, body in blocks:
        n = int(s_num)
        if n == last + 1 or (n > last and n <= last + 5 and n <= max_num + 5):
            body_clean = re.sub(r'\s+', ' ', body.strip())
            if len(body_clean) < 15:
                continue
            ex_dict[str(n)] = body_clean
            last = n
    return ex_dict


def topic_for(grade: int, part: int, num: int) -> tuple[str, str]:
    if grade == 2:
        if part == 1:
            bands = [
                (35, 'Текст и речь', 'Речь устная и письменная, текст и предложение'),
                (70, 'Предложение', 'Главные члены: подлежащее и сказуемое'),
                (110, 'Лексика', 'Слово и его значение, синонимы и антонимы'),
                (150, 'Фонетика и графика', 'Звуки и буквы, алфавит, гласные и согласные'),
                (185, 'Слог и перенос', 'Слоги, ударение и правила переноса слов'),
                (999, 'Орфография', 'Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'),
            ]
        else:
            bands = [
                (35, 'Орфография', 'Разделительный Ь и Ъ, мягкий знак'),
                (70, 'Орфография', 'Парные звонкие и глухие согласные в корне'),
                (110, 'Орфография', 'Безударные гласные в корне слова'),
                (140, 'Состав слова', 'Родственные слова и корень слова'),
                (165, 'Части речи', 'Слова-предметы, признаки и действия'),
                (999, 'Итоговое повторение', 'Итоговое повторение программы 2 класса'),
            ]
    elif grade == 3:
        bands = [
            (80, 'Повторение', 'Повторение изученного во 2 классе'),
            (160, 'Состав слова', 'Корень, приставка, суффикс, окончание'),
            (240, 'Части речи', 'Имя существительное и имя прилагательное'),
            (999, 'Глагол и предложение', 'Глагол, предложение, знаки препинания'),
        ]
    elif grade == 4:
        bands = [
            (80, 'Повторение', 'Повторение изученного в 3 классе'),
            (160, 'Орфография', 'Безударные гласные, парные и непроизносимые согласные'),
            (240, 'Морфология', 'Существительное, прилагательное, глагол, местоимение'),
            (999, 'Синтаксис', 'Простое предложение и однородные члены'),
        ]
    elif grade == 5:
        if part == 1:
            bands = [
                (40, 'Повторение и речь', 'Повторение изученного в начальной школе'),
                (100, 'Текстоведение', 'Текст, тема, основная мысль и типы речи'),
                (160, 'Фонетика и орфоэпия', 'Звуки речи, ударение и орфоэпические нормы'),
                (999, 'Графика и орфография', 'Безударные гласные и парные согласные'),
            ]
        else:
            bands = [
                (70, 'Лексика и фразеология', 'Лексическое значение, синонимы, антонимы, фразеологизмы'),
                (140, 'Морфемика', 'Состав слова, чередование гласных в корнях'),
                (220, 'Морфология', 'Имя существительное и имя прилагательное'),
                (999, 'Глагол и синтаксис', 'Глагол, синтаксический разбор и повторение'),
            ]
    elif grade == 6:
        bands = [
            (60, 'Повторение', 'Повторение изученного в 5 классе и стили речи'),
            (140, 'Лексика и фразеология', 'Исконные и заимствованные слова, фразеологизмы'),
            (220, 'Словообразование', 'Способы образования слов'),
            (350, 'Морфология', 'Имя существительное, прилагательное, числительное'),
            (999, 'Глагол и речь', 'Глагол, текст, повторение'),
        ]
    elif grade == 7:
        bands = [
            (80, 'Повторение', 'Повторение изученного в 6 классе'),
            (180, 'Причастие', 'Причастие и причастный оборот'),
            (280, 'Деепричастие', 'Деепричастие и деепричастный оборот'),
            (360, 'Наречие', 'Наречие и слова категории состояния'),
            (999, 'Служебные части речи', 'Предлог, союз, частица, междометие'),
        ]
    elif grade == 8:
        bands = [
            (80, 'Словосочетание', 'Словосочетание и виды связи'),
            (180, 'Простое предложение', 'Главные и второстепенные члены'),
            (300, 'Осложнённое предложение', 'Однородные члены, обособления, вводные'),
            (999, 'Пунктуация и текст', 'Тире, запятые, стили речи'),
        ]
    elif grade == 9:
        bands = [
            (80, 'Сложное предложение', 'Сложносочинённое предложение'),
            (180, 'СПП', 'Сложноподчинённое предложение'),
            (280, 'Бессоюзное', 'Бессоюзное сложное предложение'),
            (999, 'Текст и речь', 'Сложные синтаксические конструкции, текст'),
        ]
    elif grade == 10:
        bands = [
            (80, 'Текст и стили речи', 'Стилистика, культура речи и текстоведение'),
            (160, 'Лексика и фразеология', 'Лексические нормы, фразеология и паронимы'),
            (250, 'Фонетика и графика', 'Фонетические нормы, графика и орфография'),
            (360, 'Морфемика и словообразование', 'Способы словообразования и правописание морфем'),
            (999, 'Морфология и орфография', 'Именные части речи и орфографические нормы'),
        ]
    else:
        bands = [
            (5, 'Текст и стили', 'Функциональные стили и культура речи'),
            (10, 'Орфография', 'Трудные случаи орфографии'),
            (16, 'Пунктуация', 'Пунктуация сложного предложения'),
            (22, 'Синтаксис', 'Синтаксис и нормы построения предложения'),
            (999, 'Подготовка к ЦТ/ЦЭ', 'Комплексный анализ текста и языковые нормы'),
        ]
    for hi, sec, top in bands:
        if num <= hi:
            return f'{grade} кл. · {sec}', top
    return f'{grade} кл. · Программа', 'Упражнения учебника'


def longest_sentence(text: str) -> str:
    chunks = re.split(r'(?<=[.!?])\s+', text)
    chunks = [c.strip() for c in chunks if len(c.strip()) >= 8]
    if not chunks:
        return text[:200]
    return max(chunks, key=len)[:400]


def get_program_context():
    subject, _ = Subject.objects.get_or_create(
        slug='russian',
        defaults={'name': 'Русский язык', 'description': 'Школьная программа РБ 1-11 класс', 'order': 1},
    )
    track = ExamTrack.objects.filter(
        subject=subject, track_type=ExamTrack.TrackType.GENERAL
    ).first()
    if not track:
        track = ExamTrack.objects.create(
            subject=subject,
            track_type=ExamTrack.TrackType.GENERAL,
            name='Школьная программа (1–11 классы)',
            grade_from=1,
            grade_to=11,
            is_active=True,
        )
    version = ContentVersion.objects.filter(subject=subject, is_current=True).first()
    if not version:
        version = ContentVersion.objects.create(
            subject=subject, year=2026, title='Учебная программа 2026', is_current=True
        )
    return subject, track, version


def ensure_topic(track, version, grade: int, sec_name: str, top_name: str) -> Topic:
    section, _ = Section.objects.get_or_create(
        exam_track=track,
        name=sec_name,
        defaults={'order': 10 + grade, 'content_version': version},
    )
    if not section.content_version_id:
        section.content_version = version
        section.save(update_fields=['content_version'])
    topic, created = Topic.objects.get_or_create(
        section=section,
        name=top_name,
        grade_level=grade,
        defaults={'is_active': True, 'order': 1},
    )
    if created:
        TopicSummary.objects.get_or_create(
            topic=topic,
            defaults={
                'title': top_name,
                'content': f'Материал учебника {grade} класса: {top_name}.',
                'key_points': sec_name,
            },
        )
    return topic


class Command(BaseCommand):
    help = 'Импорт учебников 1–11 в базу (страницы 1 кл. + полный текст упражнений 2–11)'

    def add_arguments(self, parser):
        parser.add_argument('--grade', default='1', help='1 или 2 или 1-11')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        raw = options['grade'].strip()
        if '-' in raw:
            a, b = raw.split('-', 1)
            grades = list(range(int(a), int(b) + 1))
        else:
            grades = [int(x) for x in raw.split(',') if x.strip()]

        _, track, version = get_program_context()
        dry = options['dry_run']
        for g in grades:
            if g == 1:
                self.import_grade1(track, version, dry)
            elif g in TEXTBOOKS:
                self.import_text_grade(g, track, version, dry)
            else:
                self.stderr.write(f'Нет учебника для класса {g}')

    def import_grade1(self, track, version, dry: bool):
        if not G1_PDF.exists():
            self.stderr.write(f'Нет файла {G1_PDF}')
            return
        self.stdout.write(self.style.NOTICE(f'1 класс: {G1_PDF.name}'))
        doc = fitz.open(G1_PDF)
        created = 0
        skipped = 0
        # печатные 4–85 = PDF 6–87
        for pdf_i in range(5, min(87, doc.page_count)):
            printed = pdf_i + 1 - G1_PDF_OFFSET
            chapter = g1_chapter(printed)
            page = doc[pdf_i]
            raw = clean_page_text(page.get_text() or '')
            source = f'{G1_SOURCE_PREFIX} {printed} ({G1_AUTHOR})'
            if Task.objects.filter(source=source).exists():
                skipped += 1
                continue
            if dry:
                created += 1
                continue
            topic = ensure_topic(
                track, version, 1, '1 кл. · Учебник Антипова', chapter
            )
            caption = raw or chapter
            question = (
                f'Страница {printed} учебника 1 класса\n'
                f'Раздел: {chapter}\n\n'
                f'{caption}\n\n'
                f'Прочитай страницу (картинка из учебника). '
                f'Как называется этот раздел?'
            )
            distractors = [t for _, t in G1_TOC if t != chapter]
            # соседние разделы — реалистичные ошибки
            idx = next(i for i, (_, t) in enumerate(G1_TOC) if t == chapter)
            nearby = []
            for j in (idx - 1, idx + 1, idx - 2, idx + 2, 0, -1):
                if 0 <= j < len(G1_TOC) and G1_TOC[j][1] != chapter:
                    nearby.append(G1_TOC[j][1])
            opts = [chapter] + [x for x in nearby if x][:3]
            while len(opts) < 4 and distractors:
                d = distractors.pop(0)
                if d not in opts:
                    opts.append(d)

            task = Task.objects.create(
                topic=topic,
                question=question,
                reading_text=caption,
                answer_format=Task.AnswerFormat.SINGLE_CHOICE,
                scoring_scheme=Task.ScoringScheme.BINARY_1,
                difficulty=Task.Difficulty.EASY,
                source=source,
                is_active=True,
            )
            pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            task.image.save(
                f'grade1_p{printed:03d}.png',
                ContentFile(pix.tobytes('png')),
                save=True,
            )
            for i, text in enumerate(opts, start=1):
                TaskOption.objects.create(
                    task=task, text=text[:500], is_correct=(i == 1), order=i
                )
            TaskSolution.objects.create(
                task=task,
                correct_answer='1',
                explanation=(
                    f'Это страница {printed} раздела «{chapter}» '
                    f'учебника Антиповой / Грабчиковой (2024).'
                ),
            )
            created += 1
            if created % 10 == 0:
                self.stdout.write(f'  стр. {printed}, создано {created}')
        doc.close()
        self.stdout.write(self.style.SUCCESS(
            f'1 класс: создано {created}, уже были {skipped}'
        ))

    def import_text_grade(self, grade: int, track, version, dry: bool):
        specs = TEXTBOOKS[grade]
        self.stdout.write(self.style.NOTICE(f'{grade} класс: извлечение упражнений'))
        deactivated = 0
        if not dry:
            fake_qs = Task.objects.filter(
                topic__grade_level=grade,
                source__startswith='Учебник «Русский язык»',
                options__text__startswith=FAKE_OPTION_PREFIXES[0],
            ).distinct()
            deactivated = fake_qs.update(is_active=False)
            extra = Task.objects.filter(
                topic__grade_level=grade,
                source__startswith='Учебник «Русский язык»',
                options__text__startswith=FAKE_OPTION_PREFIXES[1],
            ).distinct()
            deactivated += extra.update(is_active=False)
            if deactivated:
                self.stdout.write(f'  отключены фейковые MCQ: {deactivated}')

        created = 0
        skipped = 0
        for spec in specs:
            pdf = spec['pdf']
            if not pdf.exists():
                self.stderr.write(f'  нет файла {pdf}')
                continue
            exercises = extract_exercises(
                pdf, spec['max_num'], spec.get('numbering', 'int')
            )
            part = spec['part']
            self.stdout.write(f'  {pdf.name}: {len(exercises)} упр.')
            for num, body in exercises.items():
                part_label = f', часть {part}' if part else ''
                source = (
                    f'Учебник «Русский язык» {grade} класс{part_label}, '
                    f'упр. {num} полный текст ({spec["author"]})'
                )
                if Task.objects.filter(source=source).exists():
                    skipped += 1
                    continue
                if dry:
                    created += 1
                    continue
                num_key = int(str(num).split('.')[0]) if str(num)[0].isdigit() else 1
                sec_name, top_name = topic_for(grade, part, num_key)
                topic = ensure_topic(track, version, grade, sec_name, top_name)
                copy_target = longest_sentence(body)
                question = (
                    f'Упражнение {num} (учебник {grade} класса{part_label})\n\n'
                    f'{body}\n\n'
                    f'Выполни упражнение по тексту учебника. '
                    f'Если нужно списать — спиши предложение. '
                    f'Если вставить буквы — напиши готовые слова.'
                )
                with transaction.atomic():
                    task = Task.objects.create(
                        topic=topic,
                        question=question,
                        reading_text=body,
                        answer_format=Task.AnswerFormat.TEXT,
                        scoring_scheme=Task.ScoringScheme.BINARY_1,
                        difficulty=Task.Difficulty.MEDIUM,
                        source=source,
                        is_active=True,
                    )
                    TaskSolution.objects.create(
                        task=task,
                        correct_answer=copy_target,
                        explanation=(
                            f'Упражнение {num} из учебника {grade} класса, '
                            f'тема «{top_name}». Образец для списывания / ориентир: {copy_target}'
                        ),
                    )
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f'{grade} класс: создано {created}, пропущено {skipped}'
        ))
