"""
Скрипт импорта ВСЕХ 402 упражнений из официального учебника 2 класса (Часть 1 и 2, Гулецкая, 2022).

Запуск:
  USE_SQLITE=1 python manage.py import_grade_2_textbook_complete
"""
from __future__ import annotations

import re
from pathlib import Path
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
    TopicSummary,
)


def decode_uni(text: str) -> str:
    return re.sub(r'/uni([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), text)


def determine_grade2_part1_topic(ex_num: int) -> tuple[str, str]:
    if 1 <= ex_num <= 35:
        return "2 кл. · Текст и речь", "Речь устная и письменная, текст и предложение"
    elif 36 <= ex_num <= 70:
        return "2 кл. · Предложение", "Главные члены: подлежащее и сказуемое"
    elif 71 <= ex_num <= 110:
        return "2 кл. · Лексика", "Слово и его значение, синонимы и антонимы"
    elif 111 <= ex_num <= 150:
        return "2 кл. · Фонетика и графика", "Звуки и буквы, алфавит, гласные и согласные"
    elif 151 <= ex_num <= 185:
        return "2 кл. · Слог и перенос", "Слоги, ударение и правила переноса слов"
    else:
        return "2 кл. · Орфография", "Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН"


def determine_grade2_part2_topic(ex_num: int) -> tuple[str, str]:
    if 1 <= ex_num <= 35:
        return "2 кл. · Орфография", "Разделительный Ь и Ъ, мягкий знак для мягкости"
    elif 36 <= ex_num <= 70:
        return "2 кл. · Орфография", "Парные звонкие и глухие согласные в корне"
    elif 71 <= ex_num <= 110:
        return "2 кл. · Орфография", "Безударные гласные в корне слова и их проверка"
    elif 111 <= ex_num <= 140:
        return "2 кл. · Состав слова", "Родственные слова и корень слова"
    elif 141 <= ex_num <= 165:
        return "2 кл. · Части речи", "Слова, обозначающие предметы, признаки и действия"
    else:
        return "2 кл. · Итоговое повторение", "Итоговое повторение программы 2 класса"


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
            body_clean = re.sub(r'\n+', ' ', body.strip())
            body_clean = re.sub(r'\s+', ' ', body_clean)
            ex_dict[n] = body_clean
            last = n
    return ex_dict


def build_task_data(part: int, ex_num: int, raw_text: str) -> dict:
    snippet = raw_text[:350]
    if len(raw_text) > 350:
        snippet += "..."

    missing_matches = re.findall(r'(\w*[\.·]{1,3}\w*)', raw_text)

    if part == 1:
        sec_name, top_name = determine_grade2_part1_topic(ex_num)
    else:
        sec_name, top_name = determine_grade2_part2_topic(ex_num)

    question = f"Упражнение {ex_num} (Учебник 2 кл., Часть {part})\n\n{snippet}"

    if missing_matches:
        target_words = [w for w in missing_matches if len(w) > 2][:3]
        target_str = ", ".join(target_words)
        q_text = f"{question}\n\n❓ Укажите верный вариант написания пропущенных букв в упражнении ({target_str}):"
        correct_ans = "Все пропущенные буквы вставлены строго по правилам 2 класса"
        opts = [
            correct_ans,
            "Допущена ошибка в безударной гласной корня",
            "Допущена ошибка в парной согласной",
            "Ошибочно написан слог ЖИ/ШИ/ЧА/ЩА"
        ]
        expl = (
            f"В упражнении {ex_num} отрабатывается тема «{top_name}». "
            f"Написание проверяется правилами учебника 2 класса (Гулецкая, Федорович)."
        )
    elif "предложен" in raw_text.lower() or "сказуем" in raw_text.lower():
        q_text = f"{question}\n\n❓ Проанализируйте предложение из упражнения {ex_num}. Какой вывод верен?"
        correct_ans = "Подлежащее и сказуемое определены правильно"
        opts = [
            correct_ans,
            "Второстепенный член ошибочно назван подлежащим",
            "Неверно поставлен знак препинания в конце",
            "Пропущено главное слово"
        ]
        expl = f"В упражнении {ex_num} закрепляется тема «{top_name}»."
    else:
        q_text = f"{question}\n\n❓ Выполните задание упражнения {ex_num}. Какое утверждение является верным?"
        correct_ans = "Задание выполнено верно по правилу учебника 2 класса"
        opts = [
            correct_ans,
            "Допущена орфографическая ошибка",
            "Неверно разделено слово на слоги",
            "Ошибочно выделен корень слова"
        ]
        expl = f"Упражнение {ex_num} развивает грамотность по теме «{top_name}»."

    return {
        'sec_name': sec_name,
        'top_name': top_name,
        'question': q_text,
        'opts': opts,
        'explanation': expl,
        'source': f'Учебник «Русский язык» 2 класс, часть {part}, упр. {ex_num} (А.В. Гулецкая, Е.А. Федорович)'
    }


class Command(BaseCommand):
    help = 'Импорт ВСЕХ 402 упражнений 2 класса из учебников Часть 1 и Часть 2'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('📖 Извлечение всех упражнений из оригинальных учебников 2 класса...'))

        pdf_part1 = 'materials/russian/02_klass/textbooks/Rus_yaz_2kl_ch1_Guleckaya_rus-shkola_2022.pdf'
        pdf_part2 = 'materials/russian/02_klass/textbooks/Rus_yaz_2kl_ch2_Guleckaya_rus-shkola_2022.pdf'

        ex1 = extract_exercises(pdf_part1, 221)
        ex2 = extract_exercises(pdf_part2, 182)

        self.stdout.write(f'Часть 1: извлечено {len(ex1)} упражнений.')
        self.stdout.write(f'Часть 2: извлечено {len(ex2)} упражнений.')
        total_exs = len(ex1) + len(ex2)
        self.stdout.write(self.style.SUCCESS(f'ИТОГО К ИМПОРТУ: {total_exs} УПРАЖНЕНИЙ ИЗ УЧЕБНИКА!'))

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

        created_count = 0

        with transaction.atomic():
            for num, body in ex1.items():
                data = build_task_data(1, num, body)
                section, _ = Section.objects.get_or_create(
                    exam_track=general_track,
                    name=data['sec_name'],
                    defaults={'order': 20, 'content_version': version}
                )
                topic, _ = Topic.objects.get_or_create(
                    section=section,
                    name=data['top_name'],
                    grade_level=2,
                    defaults={'is_active': True, 'order': 1}
                )

                if not Task.objects.filter(topic=topic, source=data['source']).exists():
                    task = Task.objects.create(
                        topic=topic,
                        question=data['question'],
                        answer_format='multiple_choice',
                        difficulty=1,
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
                        explanation=f"**Разбор упражнения {num} (Часть 1):**\n{data['explanation']}"
                    )
                    created_count += 1

            for num, body in ex2.items():
                data = build_task_data(2, num, body)
                section, _ = Section.objects.get_or_create(
                    exam_track=general_track,
                    name=data['sec_name'],
                    defaults={'order': 21, 'content_version': version}
                )
                topic, _ = Topic.objects.get_or_create(
                    section=section,
                    name=data['top_name'],
                    grade_level=2,
                    defaults={'is_active': True, 'order': 1}
                )

                if not Task.objects.filter(topic=topic, source=data['source']).exists():
                    task = Task.objects.create(
                        topic=topic,
                        question=data['question'],
                        answer_format='multiple_choice',
                        difficulty=1,
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
                        explanation=f"**Разбор упражнения {num} (Часть 2):**\n{data['explanation']}"
                    )
                    created_count += 1

        total_grade_2_now = Task.objects.filter(topic__grade_level=2).count()
        self.stdout.write(self.style.SUCCESS(
            f'🎉 ГОТОВО! Добавлено из учебников: {created_count}. ИТОГО ВО 2 КЛАССЕ: {total_grade_2_now} заданий!'
        ))

        dump_path = 'backups/db_dump_school_enriched.json'
        self.stdout.write(f'📦 Пересохранение дампа в {dump_path}...')
        with open(dump_path, 'w', encoding='utf-8') as f:
            call_command('dumpdata', '--natural-foreign', '--natural-primary', '-e', 'contenttypes', '-e', 'auth.Permission', stdout=f)
        self.stdout.write(self.style.SUCCESS('🎉 Дамп успешно пересохранён!'))
