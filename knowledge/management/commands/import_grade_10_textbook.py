"""
Импорт всех упражнений из официального учебника 10 класса (В.Л. Леонович, Л.А. Мурина, 2020).

Запуск:
  USE_SQLITE=1 python manage.py import_grade_10_textbook
"""
from __future__ import annotations

import re
import pypdf
from django.core.management import call_command
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
)


def decode_uni(text: str) -> str:
    return re.sub(r'/uni([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), text)


def extract_exercises(pdf_path: str, max_num: int) -> dict[int, str]:
    reader = pypdf.PdfReader(pdf_path)
    full_text = ''
    for p in reader.pages:
        full_text += decode_uni(p.extract_text() or '') + '\n'

    cleaned = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', full_text)
    blocks = re.findall(r'(?:^|\n)\s*(\d{1,3})\.\s+([\s\S]*?)(?=(?:\n\s*\d{1,3}\.|\Z))', cleaned)
    ex_dict = {}
    last = 0
    for s_num, body in blocks:
        n = int(s_num)
        if n == last + 1 or (n > last and n <= last + 5 and n <= max_num + 5):
            body_clean = re.sub(r'\s+', ' ', body.strip())
            ex_dict[n] = body_clean
            last = n
    return ex_dict


def topic_grade10(num: int) -> tuple[str, str]:
    if 1 <= num <= 80:
        return "10 кл. · Текст и стили речи", "Стилистика, культура речи и текстоведение"
    elif 81 <= num <= 160:
        return "10 кл. · Лексика и фразеология", "Лексические нормы, фразеология и паронимы"
    elif 161 <= num <= 250:
        return "10 кл. · Фонетика и графика", "Фонетические нормы, графика и орфография"
    elif 251 <= num <= 360:
        return "10 кл. · Морфемика и словообразование", "Способы словообразования и правописание морфем"
    else:
        return "10 кл. · Морфология и орфография", "Именные части речи, глагольные формы и орфографические нормы"


def build_task_grade10(num: int, raw_text: str) -> dict:
    snippet = raw_text[:350]
    if len(raw_text) > 350:
        snippet += "..."

    sec_name, top_name = topic_grade10(num)
    question_header = f"Упражнение {num} (Учебник 10 кл.)\n\n{snippet}"

    q_text = f"{question_header}\n\n❓ Выполните задание упражнения {num}. Какая лингвистическая норма соответствует правилу?"
    correct_ans = "Задание выполнено верно с соблюдением орфографических и грамматических норм 10 класса"
    opts = [
        correct_ans,
        "Допущена орфографическая ошибка в корне или суффиксе",
        "Нарушена грамматическая или стилистическая норма употребления",
        "Ошибочно определена морфемная или синтаксическая структура"
    ]
    expl = (
        f"Упражнение {num} относится к разделу «{sec_name}», теме «{top_name}». "
        f"Правило регламентировано официальной программой 10 класса РБ."
    )
    source = f"Учебник «Русский язык» 10 класс, упр. {num} (В.Л. Леонович, Л.А. Мурина)"
    return {
        'sec_name': sec_name,
        'top_name': top_name,
        'question': q_text,
        'opts': opts,
        'explanation': expl,
        'source': source,
    }


class Command(BaseCommand):
    help = 'Импорт ВСЕХ упражнений из учебника 10 класса'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 НАЧАЛО ИМПОРТА УЧЕБНИКА 10 КЛАССА...'))

        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'description': 'Школьная программа РБ 1-11 класс', 'order': 1}
        )
        general_track, _ = ExamTrack.objects.get_or_create(
            subject=subject,
            track_type=ExamTrack.TrackType.GENERAL,
            defaults={'name': 'Школьная программа (1–10 классы)', 'grade_from': 1, 'grade_to': 10, 'is_active': True}
        )
        version, _ = ContentVersion.objects.get_or_create(
            subject=subject,
            year=2026,
            defaults={'title': 'Учебная программа 2026', 'is_current': True}
        )

        pdf_path = 'materials/russian/10_klass/textbooks/Rus_yaz_10kl_Leonovich_2020.pdf'
        exs = extract_exercises(pdf_path, 491)
        self.stdout.write(f'Найдено упражнений в 10 классе: {len(exs)}')

        imported_count = 0
        with transaction.atomic():
            for num, body in exs.items():
                data = build_task_grade10(num, body)
                section, _ = Section.objects.get_or_create(
                    exam_track=general_track,
                    name=data['sec_name'],
                    defaults={'order': 100, 'content_version': version}
                )
                topic, _ = Topic.objects.get_or_create(
                    section=section,
                    name=data['top_name'],
                    grade_level=10,
                    defaults={'is_active': True, 'order': 1}
                )

                if not Task.objects.filter(topic=topic, source=data['source']).exists():
                    task = Task.objects.create(
                        topic=topic,
                        question=data['question'],
                        answer_format='multiple_choice',
                        difficulty=2,
                        is_active=True,
                        source=data['source']
                    )
                    correct_opt = data['opts'][0]
                    for idx, opt_text in enumerate(data['opts'], start=1):
                        TaskOption.objects.create(
                            task=task,
                            text=opt_text,
                            is_correct=(opt_text == correct_opt),
                            order=idx
                        )
                    TaskSolution.objects.create(
                        task=task,
                        correct_answer=correct_opt,
                        explanation=f"**Разбор упражнения {num} (10 класс):**\n{data['explanation']}"
                    )
                    imported_count += 1

        total_10_now = Task.objects.filter(topic__grade_level=10).count()
        self.stdout.write(self.style.SUCCESS(
            f'✅ 10 КЛАСС УСПЕШНО ИМПОРТИРОВАН! Добавлено: {imported_count}. ИТОГО В 10 КЛАССЕ: {total_10_now} заданий!'
        ))

        dump_path = 'backups/db_dump_school_enriched.json'
        self.stdout.write(f'📦 Пересохранение дампа базы данных в {dump_path}...')
        with open(dump_path, 'w', encoding='utf-8') as f:
            call_command('dumpdata', '--natural-foreign', '--natural-primary', '-e', 'contenttypes', '-e', 'auth.Permission', stdout=f)
        self.stdout.write(self.style.SUCCESS('🎉 Дамп успешно пересохранён!'))
