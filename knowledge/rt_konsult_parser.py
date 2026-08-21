"""Парсер РТ/ДРТ «тематическое консультирование»: вопрос + Ответ: … + разбор."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from knowledge.pdf_parser import ParsedTask, extract_numbered_options


@dataclass
class ParsedKonsultFile:
    filename: str
    label: str  # РТ 2024 этап1 в1 / ДРТ 2021
    tasks: list[ParsedTask]


TASK_SPLIT = re.compile(r'(?=(?:^|\n)\s*([АAВB])\s*(\d+)\.\s*)')
ANSWER_RE = re.compile(r'(?i)\n\s*Ответ\s*:\s*([^\n]+)')


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    if getattr(reader, 'is_encrypted', False):
        # РИКЗ часто ставит пустой user-password (нужен пакет cryptography)
        try:
            reader.decrypt('')
        except Exception:
            pass
    text = '\n'.join((page.extract_text() or '') for page in reader.pages)
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def label_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = stem.replace('_konsultaciya_otvety', '').replace('_konsultaciya', '')
    stem = stem.replace('_zadaniya', ' задания')
    return stem.replace('_', ' ')


def parse_konsult_pdf(path: Path) -> ParsedKonsultFile:
    text = extract_text(path)
    tasks: list[ParsedTask] = []
    # Find all task starts
    starts = list(re.finditer(r'(?:^|\n)\s*([АAВB])\s*(\d+)\.\s+', text))
    for i, m in enumerate(starts):
        letter = m.group(1).upper().replace('A', 'А').replace('B', 'В')
        num = int(m.group(2))
        start = m.end()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[start:end]
        am = ANSWER_RE.search(block)
        if not am:
            continue
        answer = re.sub(r'\s+', ' ', am.group(1)).strip().rstrip('.')
        # normalize "1, 2, 3"
        answer = re.sub(r'\s*,\s*', ', ', answer)
        question_body = block[: am.start()].strip()
        explanation = block[am.end() :].strip()
        # trim explanation to before next big header noise
        explanation = re.split(r'\n(?:Русский язык: учеб|Учреждение образования)', explanation)[0]
        explanation = re.sub(r'\s+', ' ', explanation).strip()[:1200]
        opts = extract_numbered_options(question_body)
        stem = re.split(r'\n\s*\d\)', question_body, maxsplit=1)[0].strip()
        stem = re.sub(r'\s+', ' ', stem)
        code = f'{letter}{num}'
        question = f'[{code}] {stem}'
        need_mc = bool(re.fullmatch(r'(?:\d(?:\s*,\s*\d)*)', answer))
        # соответствия А1Б2В3Г4 — текстовый ключ, не MCQ
        if re.fullmatch(r'(?:[АA]\d[БB]\d[ВV]\d[ГG]\d)', answer, re.I):
            need_mc = False
            answer = answer.upper().replace('A', 'А').replace('B', 'Б').replace('V', 'В').replace('G', 'Г')
        fmt = 'multiple_choice' if need_mc and len(opts) >= 2 else 'text'
        if fmt == 'multiple_choice':
            max_opt = max(int(x) for x in answer.split(',') if x.strip().isdigit())
            while len(opts) < max_opt:
                opts.append(f'(вариант {len(opts) + 1})')
            opts = [o[:490] for o in opts]
        elif opts:
            question += '\n' + '\n'.join(f'{j}) {o[:200]}' for j, o in enumerate(opts, 1))
            opts = []
        # убрать колонтитулы из вопроса
        question = re.sub(r'РТ–\d{4}/\d{4} гг\..*', '', question).strip()
        question = question[:4000]
        # stash explanation
        payload = f'{answer}|||{explanation}' if explanation else answer
        tasks.append(
            ParsedTask(
                number=len(tasks) + 1,
                question=question,
                correct_answer=payload,
                answer_format=fmt,
                option_labels=opts,
            )
        )

    return ParsedKonsultFile(
        filename=path.name,
        label=label_from_filename(path.name),
        tasks=tasks,
    )


def parse_all_konsult(dirs: list[Path]) -> list[ParsedKonsultFile]:
    files: list[ParsedKonsultFile] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob('*.pdf')):
            # skip pure zadaniya without answers (pair with otvety separately)
            if path.name.endswith('_zadaniya.pdf'):
                continue
            try:
                parsed = parse_konsult_pdf(path)
            except Exception:
                continue
            if parsed.tasks:
                files.append(parsed)
    return files
