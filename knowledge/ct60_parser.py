"""Парсер пособия «Русский язык. ЦТ за 60 уроков» (Бычковская и др.)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from knowledge.pdf_parser import ParsedTask, extract_numbered_options


@dataclass
class ParsedCt60Section:
    section_title: str
    test_number: int
    tasks: list[ParsedTask] = field(default_factory=list)


KEY_HEADER = re.compile(r'КЛЮЧИ И КОММЕНТАРИИ К ТЕСТАМ')
KEY_TEST = re.compile(
    r'Тест\s+(\d+)\s*\n\s*Задание\s+Ключи\s+Комментарии\s*(.*?)'
    r'(?=\nТест\s+\d+\s*\n\s*Задание\s+Ключи|\Z)',
    re.S | re.I,
)
Q_TEST = re.compile(
    r'(?:^|\n)Тест\s+(\d+)\s*\n(?!\s*Задание\s+Ключи)(.*?)'
    r'(?=(?:\nТест\s+\d+\s*\n)|(?:\nКЛЮЧИ И КОММЕНТАРИИ)|\Z)',
    re.S | re.I,
)
KEY_LINE = re.compile(
    r'^(\d{1,2})\s+((?:\d(?:\s*,\s*\d)*)|(?:А\dБ\dВ\dГ\d))\s*(.*)$'
)


def extract_ct60_text(path: Path) -> str:
    reader = PdfReader(str(path))
    chunks = [(page.extract_text() or '') for page in reader.pages]
    text = '\n'.join(chunks)
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def _guess_section_title(prev_chunk: str) -> str:
    markers = {
        'ОРФОГРАФИЯ': 'Орфография',
        'ПУНКТУАЦИЯ': 'Пунктуация',
        'ЛЕКСИКА': 'Лексика',
        'ФРАЗЕОЛОГИЯ': 'Лексика. Фразеология',
        'МОРФОЛОГИЯ': 'Морфология',
        'СИНТАКСИС': 'Синтаксис',
        'ФОНЕТИКА': 'Фонетика',
        'СЛОВООБРАЗОВАНИЕ': 'Словообразование',
        'КУЛЬТУРА РЕЧИ': 'Культура речи',
        'ИТОГОВЫЕ ТЕСТЫ': 'Итоговые тесты',
        'ДИАГНОСТИЧЕСКИЕ ТЕСТЫ': 'Диагностические тесты',
    }
    upper = prev_chunk.upper()
    best_pos = -1
    best = 'ЦТ за 60 уроков'
    for key, title in markers.items():
        pos = upper.rfind(key)
        if pos > best_pos:
            best_pos = pos
            best = title
    return best


def parse_keys_block(block: str) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}
    cur_num = None
    cur_ans = None
    cur_expl: list[str] = []
    for raw in block.split('\n'):
        line = raw.strip()
        if not line:
            continue
        m = KEY_LINE.match(line)
        if m:
            if cur_num is not None and cur_ans is not None:
                out[cur_num] = (cur_ans, ' '.join(cur_expl).strip())
            cur_num = int(m.group(1))
            cur_ans = re.sub(r'\s*,\s*', ', ', m.group(2).strip())
            tail = m.group(3).strip()
            cur_expl = [tail] if tail else []
        elif cur_num is not None:
            cur_expl.append(line)
    if cur_num is not None and cur_ans is not None:
        out[cur_num] = (cur_ans, ' '.join(cur_expl).strip())
    return out


def parse_questions(block: str) -> dict[int, tuple[str, list[str]]]:
    out: dict[int, tuple[str, list[str]]] = {}
    matches = list(re.finditer(r'(?:^|\n)\s*(\d{1,2})\.\s+', block))
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if num > 40:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        body = block[start:end].strip()
        body = re.split(
            r'\n(?:УРОК|РАЗМИНКА|ОРФОГРАФИЯ|ПУНКТУАЦИЯ|ЛЕКСИКА|СИНТАКСИС|'
            r'ИТОГОВ|МОРФОЛОГИЯ|ФОНЕТИКА|К читателю)',
            body,
        )[0].strip()
        opts = extract_numbered_options(body)
        if len(opts) < 2:
            # fallback: looser option grab
            opts = []
            for om in re.finditer(
                r'(?:^|\n)\s*(\d)\)\s*([^\n]+(?:\n(?!\s*\d\))[^\n]+)*)',
                body,
            ):
                opts.append(re.sub(r'\s+', ' ', om.group(2)).strip().rstrip(';.,'))
        stem = re.split(r'\n\s*\d\)', body, maxsplit=1)[0].strip()
        stem = re.sub(r'\s+', ' ', stem)
        if len(stem) < 5 and not opts:
            continue
        out[num] = (stem or re.sub(r'\s+', ' ', body)[:400], opts)
    return out


def parse_ct60_pdf(path: Path) -> list[ParsedCt60Section]:
    text = extract_ct60_text(path)
    parts = re.split(r'(?=КЛЮЧИ И КОММЕНТАРИИ К ТЕСТАМ)', text)
    sections: list[ParsedCt60Section] = []
    global_num = 0

    for i, part in enumerate(parts):
        if not KEY_HEADER.match(part):
            continue
        prev = parts[i - 1] if i > 0 else ''
        section_title = _guess_section_title(prev)

        key_tests: dict[int, dict[int, tuple[str, str]]] = {}
        for m in KEY_TEST.finditer(part):
            key_tests[int(m.group(1))] = parse_keys_block(m.group(2))

        q_tests: dict[int, dict[int, tuple[str, list[str]]]] = {}
        for m in Q_TEST.finditer(prev):
            q_tests[int(m.group(1))] = parse_questions(m.group(2))

        for test_num, keys in sorted(key_tests.items()):
            qs = q_tests.get(test_num, {})
            tasks: list[ParsedTask] = []
            for qnum, (answer, explanation) in sorted(keys.items()):
                if qnum not in qs:
                    continue
                stem, opts = qs[qnum]
                # если ключ ссылается на варианты, которых нет — всё равно сохраняем
                need_opts = bool(re.fullmatch(r'(?:\d(?:\s*,\s*\d)*)', answer))
                fmt = 'multiple_choice' if need_opts and len(opts) >= 2 else 'text'
                # если MCQ, но опций меньше max(answer) — добьём заглушками
                if fmt == 'multiple_choice':
                    max_opt = max(int(x) for x in answer.split(',') if x.strip().isdigit())
                    while len(opts) < max_opt:
                        opts.append(f'(вариант {len(opts) + 1} — см. PDF)')
                global_num += 1
                question = f'[Тест {test_num} · №{qnum}] {stem}'
                if opts and fmt == 'text':
                    # приложим варианты к тексту
                    question += '\n' + '\n'.join(f'{i}) {o}' for i, o in enumerate(opts, 1))
                tasks.append(
                    ParsedTask(
                        number=global_num,
                        question=question,
                        correct_answer=answer,
                        answer_format=fmt,
                        option_labels=opts if fmt == 'multiple_choice' else [],
                    )
                )
                # explanation stored via correct_answer only in ParsedTask —
                # importer will put explanation in TaskSolution; stash in question note? 
                # Use option_labels empty and put explanation after answer with separator? 
                # Better: extend dataclass usage — store in correct_answer metadata.
                # We'll attach explanation by encoding: answer|||explanation in importer path.
                tasks[-1].correct_answer = f'{answer}|||{explanation}' if explanation else answer

            if tasks:
                sections.append(
                    ParsedCt60Section(
                        section_title=section_title,
                        test_number=test_num,
                        tasks=tasks,
                    )
                )
    return sections
