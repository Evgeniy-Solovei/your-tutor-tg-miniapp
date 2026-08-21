"""
Импорт текстов изложений 9 класса из PDF сборника НИО.

  python manage.py import_grade9_izlozheniya
  python manage.py import_grade9_izlozheniya --clear
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.izlozhenie import build_izlozhenie_question, parse_izlozhenie_question
from knowledge.models import (
    ContentVersion,
    ExamTrack,
    Section,
    Subject,
    Task,
    TaskSolution,
    TaskType,
    Topic,
    TopicSummary,
)

DEFAULT_PDF = (
    Path(settings.BASE_DIR)
    / 'materials'
    / 'russian'
    / '09_klass'
    / 'exam_texts'
    / 'sbornik-izlozheniy-NIO-Galkina_2022.pdf'
)

SOURCE_LABEL = 'Сборник изложений НИО (Галкина и др., 2022)'


def _parse_toc(toc_text: str) -> list[str]:
    idx = toc_text.find('Содержание')
    if idx < 0:
        return []
    toc_text = toc_text[idx:]
    entries: list[str] = []
    for line in toc_text.splitlines():
        line = line.strip()
        m = re.match(r'^(.+?)\s+\.{2,}\s+(\d+)\s*$', line)
        if not m:
            continue
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        if title.lower() in ('от составителей', 'содержание', 'список источников'):
            continue
        entries.append(title)
    return entries


def _find_title(text: str, title: str, start: int = 0) -> int:
    parts = re.split(r'\s+', title)
    pat = r'\s+'.join(re.escape(p) for p in parts)
    m = re.search(pat, text[start:], flags=re.IGNORECASE)
    return (start + m.start()) if m else -1


def extract_izlozheniya(pdf_path: Path) -> list[tuple[str, int, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    toc_text = ''
    for i in range(max(0, len(reader.pages) - 4), max(0, len(reader.pages) - 1)):
        toc_text += (reader.pages[i].extract_text() or '') + '\n'
    titles = _parse_toc(toc_text)
    if not titles:
        raise ValueError('Не удалось прочитать оглавление сборника')

    joined = '\n'.join((p.extract_text() or '') for p in reader.pages)
    joined = re.sub(r'\n\d{1,3}\s+\d{1,3}\n', '\n', joined)
    joined = re.sub(r'(?m)^\d{1,3}$', '', joined)
    for marker in ('Список источников', '\nСодержание\n'):
        cut = joined.find(marker)
        if cut > 0:
            joined = joined[:cut]
            break

    positions: list[tuple[str, int]] = []
    cursor = 0
    for title in titles:
        pos = _find_title(joined, title, cursor)
        positions.append((title, pos))
        if pos >= 0:
            cursor = pos + 5

    results: list[tuple[str, int, str]] = []
    for i, (title, pos) in enumerate(positions):
        if pos < 0:
            continue
        end = next(
            (positions[j][1] for j in range(i + 1, len(positions)) if positions[j][1] > pos),
            len(joined),
        )
        chunk = joined[pos:end]
        parts = re.split(r'\s+', title)
        pat = r'\s+'.join(re.escape(p) for p in parts)
        body = re.sub(r'^' + pat, '', chunk, count=1, flags=re.I)
        body = re.sub(r'\s+', ' ', body).strip()
        m = re.search(r'\((\d+)\s*слов[ао]?\.?\)', body)
        if not m:
            continue
        word_count = int(m.group(1))
        body = body[: m.start()].strip()
        # убираем артефакты переносов: «бла- годарны» → «благодарны»
        body = re.sub(r'(\w)-\s+(\w)', r'\1\2', body)
        if len(body.split()) < 120:
            continue
        results.append((title, word_count, body))
    return results


class Command(BaseCommand):
    help = 'Импорт текстов изложений 9 класса из PDF в задания (текстовый ответ)'

    def add_arguments(self, parser):
        parser.add_argument('--pdf', type=str, default=str(DEFAULT_PDF))
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Удалить ранее импортированные задания из этого сборника',
        )

    def handle(self, *args, **options):
        pdf_path = Path(options['pdf'])
        if not pdf_path.exists():
            self.stderr.write(self.style.ERROR(f'PDF не найден: {pdf_path}'))
            return

        self.stdout.write(f'Читаю {pdf_path}…')
        texts = extract_izlozheniya(pdf_path)
        self.stdout.write(f'Извлечено текстов: {len(texts)}')

        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'is_active': True},
        )
        track = ExamTrack.objects.filter(
            subject=subject,
            track_type=ExamTrack.TrackType.ATTESTAT_9,
        ).first()
        if not track:
            self.stderr.write(
                self.style.ERROR('Нет трека attestat_9 — сначала: python manage.py import_grade9_attestat')
            )
            return

        version, _ = ContentVersion.objects.update_or_create(
            subject=subject,
            year=2022,
            title='Сборник текстов для изложений (НИО)',
            defaults={
                'notes': str(pdf_path.relative_to(settings.BASE_DIR)),
                'is_current': False,
            },
        )

        with transaction.atomic():
            if options['clear']:
                deleted, _ = Task.objects.filter(source=SOURCE_LABEL).delete()
                self.stdout.write(f'Удалено старых заданий: {deleted}')

            section, _ = Section.objects.get_or_create(
                exam_track=track,
                content_version=version,
                name='Тексты для изложений (выпускной экзамен)',
                defaults={'order': 100},
            )
            topic, _ = Topic.objects.get_or_create(
                section=section,
                name='Подробное изложение',
                defaults={
                    'grade_level': 9,
                    'exam_weight': 3.0,
                    'order': 1,
                    'is_active': True,
                },
            )
            TopicSummary.objects.update_or_create(
                topic=topic,
                defaults={
                    'title': 'Изложение — форма выпускного экзамена 9 класса',
                    'content': (
                        'Прослушай/прочитай текст, напиши подробное изложение. '
                        'Следи за орфографией, пунктуацией и передачей смысла. '
                        'Объём исходного текста — около 240–300 слов.'
                    ),
                    'key_points': (
                        'Передай основное содержание; сохрани стиль; '
                        'проверь сложные предложения и знаки препинания.'
                    ),
                    'source_note': SOURCE_LABEL,
                },
            )
            task_type, _ = TaskType.objects.get_or_create(
                exam_track=track,
                code='izlozhenie',
                defaults={
                    'name': 'Изложение',
                    'description': 'Письменный пересказ текста (выпускной экзамен II ступени)',
                    'max_score': 2,
                    'order': 1,
                },
            )

            created = 0
            updated = 0
            for order, (title, word_count, body) in enumerate(texts, start=1):
                question = build_izlozhenie_question(title, word_count, body)
                existing = (
                    Task.objects.filter(topic=topic, source=SOURCE_LABEL)
                    .filter(question__contains=f'Заголовок: {title}')
                    .first()
                )
                if existing is None:
                    # старый формат импорта
                    existing = (
                        Task.objects.filter(topic=topic, source=SOURCE_LABEL)
                        .filter(question__startswith=f'Изложение: «{title}»')
                        .first()
                    )

                if existing:
                    existing.question = question
                    existing.task_type = task_type
                    existing.answer_format = Task.AnswerFormat.TEXT
                    existing.scoring_scheme = Task.ScoringScheme.PARTIAL_2
                    existing.is_active = True
                    existing.save(
                        update_fields=[
                            'question',
                            'task_type',
                            'answer_format',
                            'scoring_scheme',
                            'is_active',
                        ]
                    )
                    TaskSolution.objects.update_or_create(
                        task=existing,
                        defaults={
                            'correct_answer': body,
                            'explanation': (
                                f'Эталон — исходный текст «{title}» ({word_count} слов) '
                                f'из официального сборника НИО. '
                                f'Оценивается передача содержания, грамотность и связность.'
                            ),
                            'common_mistakes': (
                                'Пропуск ключевых фактов; искажение смысла; '
                                'ошибки в сложных предложениях и причастиях.'
                            ),
                        },
                    )
                    updated += 1
                    continue

                task = Task.objects.create(
                    topic=topic,
                    task_type=task_type,
                    question=question,
                    answer_format=Task.AnswerFormat.TEXT,
                    scoring_scheme=Task.ScoringScheme.PARTIAL_2,
                    difficulty=Task.Difficulty.MEDIUM,
                    source=SOURCE_LABEL,
                    is_active=True,
                )
                TaskSolution.objects.create(
                    task=task,
                    correct_answer=body,
                    explanation=(
                        f'Эталон — исходный текст «{title}» ({word_count} слов). '
                        f'Оценивается передача содержания, грамотность и связность речи.'
                    ),
                    common_mistakes=(
                        'Пропуск ключевых фактов; искажение смысла; '
                        'ошибки в сложных предложениях и причастиях.'
                    ),
                )
                created += 1

        sample = parse_izlozhenie_question(
            Task.objects.filter(topic=topic, source=SOURCE_LABEL).first().question
        )
        self.stdout.write(self.style.SUCCESS(
            f'Готово: создано {created}, обновлено {updated}. '
            f'Тема: «{topic.name}». Пример: «{sample.title}».'
        ))
