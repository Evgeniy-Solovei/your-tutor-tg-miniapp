"""Чинит задания-страницы 1 класса: картинка из учебника → нормальный вопрос.

Было: свалка OCR + «Как называется этот раздел?»
Стало: «Посмотри на картинку» + вопрос по смыслу страницы.
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.g1_toc import G1_TOC
from knowledge.models import Task, TaskOption, TaskSolution

PAGE_SOURCE_MARK = ', стр.'


def _page_num_from_source(source: str) -> int | None:
    m = re.search(r',\s*стр\.\s*(\d+)', source or '')
    return int(m.group(1)) if m else None


def _chapter_for_page(printed: int) -> str:
    chapter = G1_TOC[0][1]
    for start, title in G1_TOC:
        if printed >= start:
            chapter = title
        else:
            break
    return chapter


def _build_question(chapter: str, page: int | None) -> str:
    return (
        'Посмотри на картинку страницы учебника.\n\n'
        'О чём эта страница?'
    )


def _build_options(chapter: str) -> list[tuple[str, bool]]:
    titles = [title for _, title in G1_TOC]
    distractors = [t for t in titles if t != chapter]
    # соседние темы — более правдоподобные ошибки
    idx = next((i for i, t in enumerate(titles) if t == chapter), 0)
    nearby = []
    for j in (idx - 1, idx + 1, idx - 2, idx + 2):
        if 0 <= j < len(titles) and titles[j] != chapter and titles[j] not in nearby:
            nearby.append(titles[j])
    for t in distractors:
        if t not in nearby and len(nearby) < 3:
            nearby.append(t)
    opts = [(chapter, True)] + [(t, False) for t in nearby[:3]]
    while len(opts) < 4 and distractors:
        d = distractors.pop(0)
        if all(d != o[0] for o in opts):
            opts.append((d, False))
    return opts[:4]


class Command(BaseCommand):
    help = 'Переписывает задания-страницы 1 класса под формат «смотри картинку» и включает их'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        qs = Task.objects.filter(source__contains=PAGE_SOURCE_MARK).select_related('topic')
        fixed = 0
        for task in qs.iterator():
            page = _page_num_from_source(task.source)
            chapter = task.topic.name if task.topic_id else (
                _chapter_for_page(page) if page else 'Русский язык'
            )
            # если тема не из оглавления — берём по номеру страницы
            toc_titles = {t for _, t in G1_TOC}
            if chapter not in toc_titles and page:
                chapter = _chapter_for_page(page)

            question = _build_question(chapter, page)
            # Текст не дублируем: ответ должен браться с картинки страницы.
            options = _build_options(chapter)
            explanation = (
                f'На странице{f" {page}" if page else ""} учебника тема «{chapter}». '
                f'Смотри на рисунки и заголовок — ответ на картинке.'
            )

            if dry:
                self.stdout.write(f'[dry] #{task.id} стр.{page} → {chapter[:40]}')
                fixed += 1
                continue

            with transaction.atomic():
                task.question = question
                task.reading_text = ''
                task.answer_format = Task.AnswerFormat.SINGLE_CHOICE
                task.is_active = True
                task.save(update_fields=[
                    'question', 'reading_text', 'answer_format', 'is_active',
                ])
                TaskOption.objects.filter(task=task).delete()
                for order, (text, is_correct) in enumerate(options, start=1):
                    TaskOption.objects.create(
                        task=task,
                        text=text[:500],
                        is_correct=is_correct,
                        order=order,
                    )
                TaskSolution.objects.update_or_create(
                    task=task,
                    defaults={
                        'correct_answer': '1',
                        'explanation': explanation,
                    },
                )
            fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {"(dry) " if dry else ""}исправлено {fixed} страниц-заданий 1 класса'
        ))
