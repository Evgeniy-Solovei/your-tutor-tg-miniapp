"""
Импорт пары ДРТ: задания + консультация с ответами/разбором.

  ./venv/bin/python manage.py import_drt_pair --year 2021
  ./venv/bin/python manage.py import_drt_pair --year 2021 --clear
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import (
    ContentVersion,
    ExamCollection,
    ExamTrack,
    Section,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    Topic,
    TopicSummary,
)
from knowledge.pdf_parser import ParsedTask, extract_numbered_options
from knowledge.rt_konsult_parser import extract_text, parse_konsult_pdf

SOURCE_PREFIX = 'ДРТ вариант'
DEFAULT_DIR = Path('materials/russian/11_klass/practice/drt')


def _parse_zadaniya(path: Path) -> dict[str, tuple[str, list[str]]]:
    text = extract_text(path)
    starts = list(re.finditer(r'(?:^|\n)\s*([АAВB])\s*(\d+)\.\s+', text))
    out: dict[str, tuple[str, list[str]]] = {}
    for i, m in enumerate(starts):
        letter = m.group(1).upper().replace('A', 'А').replace('B', 'В')
        code = f'{letter}{int(m.group(2))}'
        start = m.end()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[start:end]
        body = re.split(r'\n(?:Вариант|Часть\s+[АABВB]|©\s*Министерство)', body)[0]
        opts = extract_numbered_options(body)
        if len(opts) < 2:
            opts = []
            for om in re.finditer(
                r'(?:^|\n)\s*(\d)\)\s*([^\n]+(?:\n(?!\s*\d\))[^\n]+)*)',
                body,
            ):
                opts.append(re.sub(r'\s+', ' ', om.group(2)).strip().rstrip(';.,')[:490])
        stem = re.split(r'\n\s*\d\)', body, maxsplit=1)[0]
        stem = re.sub(r'\s+', ' ', stem).strip()
        stem = re.sub(r'ДРТ-\d{4}\.\s*\d*\s*', '', stem).strip()
        if len(stem) < 5 and not opts:
            continue
        out[code] = (stem[:1500], opts)
    return out


def _answers_from_konsult(path: Path) -> dict[str, tuple[str, str]]:
    bank = parse_konsult_pdf(path)
    out: dict[str, tuple[str, str]] = {}
    for t in bank.tasks:
        m = re.match(r'\[([АAВB]\d+)\]', t.question)
        if not m:
            continue
        code = m.group(1).upper().replace('A', 'А').replace('B', 'В')
        if '|||' in t.correct_answer:
            ans, expl = t.correct_answer.split('|||', 1)
        else:
            ans, expl = t.correct_answer, ''
        out[code] = (ans.strip(), expl.strip())
    return out


def build_drt_pair(zadaniya: Path, konsult: Path) -> list[ParsedTask]:
    questions = _parse_zadaniya(zadaniya)
    answers = _answers_from_konsult(konsult)
    tasks: list[ParsedTask] = []
    for code in sorted(set(questions) & set(answers), key=lambda c: (c[0], int(c[1:]))):
        stem, opts = questions[code]
        answer, expl = answers[code]
        need_mc = bool(re.fullmatch(r'(?:\d(?:\s*,\s*\d)*)', answer.replace(' ', '')))
        if re.search(r'[АA]\d[БB]\d', answer, re.I):
            need_mc = False
        fmt = 'multiple_choice' if need_mc and len(opts) >= 2 else 'text'
        if fmt == 'multiple_choice':
            digits = [int(x.strip()) for x in answer.split(',') if x.strip().isdigit()]
            max_opt = max(digits) if digits else len(opts)
            while len(opts) < max_opt:
                opts.append(f'(вариант {len(opts) + 1})')
            opts = [o[:490] for o in opts]
        elif opts:
            stem = stem + '\n' + '\n'.join(f'{j}) {o}' for j, o in enumerate(opts, 1))
            opts = []
        payload = f'{answer}|||{expl}' if expl else answer
        tasks.append(
            ParsedTask(
                number=len(tasks) + 1,
                question=f'[{code}] {stem}'[:4000],
                correct_answer=payload,
                answer_format=fmt,
                option_labels=opts,
            )
        )
    return tasks


class Command(BaseCommand):
    help = 'Импорт ДРТ: PDF заданий + PDF консультации (ответы/разбор)'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=2021)
        parser.add_argument('--clear', action='store_true')
        parser.add_argument('--dir', default=str(DEFAULT_DIR))

    def handle(self, *args, **options):
        year = options['year']
        base = Path(options['dir'])
        if not base.is_absolute():
            base = Path(settings.BASE_DIR) / base
        zad = base / f'DRT_{year}_zadaniya.pdf'
        kon = base / f'DRT_{year}_konsultaciya_otvety.pdf'
        if not zad.exists() or not kon.exists():
            self.stderr.write(self.style.ERROR(f'Нужны {zad.name} и {kon.name}'))
            return

        tasks = build_drt_pair(zad, kon)
        self.stdout.write(f'Разобрано: {len(tasks)}')

        prefix = f'{SOURCE_PREFIX} {year}'
        with transaction.atomic():
            subject, track, version = self._ensure_structure(year)
            if options['clear']:
                deleted, _ = Task.objects.filter(source__startswith=prefix).delete()
                self.stdout.write(f'Удалено: {deleted}')

            section, _ = Section.objects.get_or_create(
                exam_track=track,
                content_version=version,
                name=f'ДРТ {year} — полный вариант',
                defaults={'order': 25},
            )
            topic, _ = Topic.objects.get_or_create(
                section=section,
                name=f'ДРТ {year}',
                defaults={
                    'grade_level': 11,
                    'exam_weight': 1.0,
                    'order': 1,
                    'is_active': True,
                },
            )
            TopicSummary.objects.update_or_create(
                topic=topic,
                defaults={
                    'title': f'ДРТ {year}',
                    'content': 'Дистанционное репетиционное тестирование РИКЗ.',
                    'key_points': 'Часть А (30) + часть В (10); ключи и разбор из консультации.',
                    'source_note': f'DRT_{year}_zadaniya + konsultaciya_otvety',
                },
            )
            created = self._import(topic, tasks, prefix)
            ExamCollection.objects.update_or_create(
                subject=subject,
                source_file=str(zad.relative_to(settings.BASE_DIR)),
                defaults={
                    'title': f'ДРТ {year} (задания + ключи)',
                    'publisher': 'РИКЗ',
                    'year': year,
                    'is_active': True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f'Импортировано: {created}'))

    def _ensure_structure(self, year: int):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={'name': 'Русский язык', 'order': 1, 'is_active': True},
        )
        track, _ = ExamTrack.objects.get_or_create(
            subject=subject,
            track_type=ExamTrack.TrackType.CT_11,
            defaults={
                'name': 'ЦТ по русскому языку (после 11 класса)',
                'grade_from': 10,
                'grade_to': 11,
                'is_active': True,
            },
        )
        version, _ = ContentVersion.objects.update_or_create(
            subject=subject,
            title=f'ДРТ {year}',
            defaults={
                'year': year,
                'is_current': False,
                'notes': 'practice/drt/',
            },
        )
        return subject, track, version

    def _import(self, topic: Topic, items: list[ParsedTask], prefix: str) -> int:
        created = 0
        for parsed in items:
            m = re.match(r'\[([АВ]\d+)\]', parsed.question)
            code = m.group(1) if m else str(parsed.number)
            source = f'{prefix} / {code}'
            if Task.objects.filter(source=source).exists():
                continue
            answer = parsed.correct_answer
            expl = ''
            if '|||' in answer:
                answer, expl = answer.split('|||', 1)
            fmt = (
                Task.AnswerFormat.MULTIPLE_CHOICE
                if parsed.answer_format == 'multiple_choice'
                else Task.AnswerFormat.TEXT
            )
            task = Task.objects.create(
                topic=topic,
                question=parsed.question,
                answer_format=fmt,
                difficulty=Task.Difficulty.MEDIUM,
                source=source,
                is_active=True,
                scoring_scheme=(
                    Task.ScoringScheme.PARTIAL_2
                    if fmt == Task.AnswerFormat.MULTIPLE_CHOICE
                    else Task.ScoringScheme.BINARY_2
                ),
            )
            if fmt == Task.AnswerFormat.MULTIPLE_CHOICE and parsed.option_labels:
                correct = {
                    int(x.strip())
                    for x in answer.split(',')
                    if x.strip().isdigit()
                }
                for idx, label in enumerate(parsed.option_labels, start=1):
                    TaskOption.objects.create(
                        task=task,
                        text=f'{idx}) {label}'[:500],
                        is_correct=idx in correct,
                        order=idx,
                    )
            elif fmt == Task.AnswerFormat.MULTIPLE_CHOICE:
                task.answer_format = Task.AnswerFormat.TEXT
                task.scoring_scheme = Task.ScoringScheme.BINARY_2
                task.save(update_fields=['answer_format', 'scoring_scheme'])

            TaskSolution.objects.create(
                task=task,
                correct_answer=answer,
                explanation=expl or f'Ключ ДРТ: {answer}',
                common_mistakes='',
            )
            created += 1
        return created
