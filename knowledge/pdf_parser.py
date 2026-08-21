"""Парсер открытого банка РИКЗ (PDF) → задания с ответами."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass
class ParsedTask:
    number: int
    question: str
    correct_answer: str
    answer_format: str  # multiple_choice | text
    option_labels: list[str] = field(default_factory=list)


@dataclass
class ParsedBankFile:
    filename: str
    section_name: str
    part_name: str
    tasks: list[ParsedTask]


SECTION_MAP = {
    '1': ('Орфография', 'орфография'),
    '2': ('Пунктуация', 'пунктуация'),
    '3': ('Лексика', 'лексика'),
    '4': ('Культура речи', 'культура-речи'),
    '5': ('Фонетика', 'фонетика'),
    '6': ('Состав слова. Образование слов', 'словообразование'),
    '7': ('Морфология', 'морфология'),
    '8': ('Синтаксис', 'синтаксис'),
    '9': ('Текст', 'текст'),
}


def section_from_filename(filename: str) -> tuple[str, str, str]:
    """Возвращает (название раздела, slug, часть).

    Поддерживает:
      1.1.pdf
      rikz_openbank_ct_ce_11__1.1__orfografiya__chast1.pdf
      rikz_openbank_ct_ce_11__3__leksika.pdf
    """
    stem = Path(filename).stem
    # номер раздела после префикса: ...__1.1__... или просто 1.1 / 3
    m = re.search(r'(?:^|__)(\d+)(?:\.(\d+))?(?:__|$)', stem)
    if not m:
        m = re.match(r'^(\d+)(?:\.(\d+))?$', stem)
    if not m:
        return ('Прочее', 'prochee', stem)
    section_num, part = m.group(1), m.group(2) or '1'
    name, slug = SECTION_MAP.get(section_num, (f'Раздел {section_num}', f'section-{section_num}'))
    return name, slug, f'Часть {part}'


def _bank_section_key(stem: str) -> str | None:
    """Ключ раздела из имени файла (1.1, 9.1, 3) или None если не банк."""
    if stem.startswith('Uch-pr') or stem.startswith('programma_') or 'unclassified' in stem:
        return None
    if stem == 'rus':
        return None
    m = re.search(r'(?:^|__)(\d+)(?:\.(\d+))?(?:__|$)', stem)
    if not m:
        m = re.match(r'^(\d+)(?:\.(\d+))?$', stem)
    if not m:
        return None
    return f'{m.group(1)}.{m.group(2)}' if m.group(2) else m.group(1)


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or '')
    text = '\n'.join(chunks)
    # нормализация типографики
    text = text.replace('ё', 'ё').replace('Ё', 'Ё')
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def split_tasks_and_answers(text: str) -> tuple[str, str]:
    # Ищем блок ОТВЕТЫ (регистр может плавать)
    match = re.search(r'\n\s*ОТВЕТЫ\s*\n', text, flags=re.IGNORECASE)
    if not match:
        # иногда "ОТВЕТЫ" без перевода строки
        match = re.search(r'\bОТВЕТЫ\b', text, flags=re.IGNORECASE)
    if not match:
        return text, ''
    return text[: match.start()], text[match.end() :]


def parse_answers(answers_text: str) -> dict[int, str]:
    """
    Парсит таблицу ответов вида:
    1 1, 3, 5  32 2, 4
    или
    11 А2Б1В5Г4
    или
    91 жуткая
    """
    answers: dict[int, str] = {}
    # Уберём заголовки
    cleaned = re.sub(r'№\s*задания\s*Ответ', ' ', answers_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'Часть\s*\d+', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace('\n', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Паттерн: номер + ответ (цифры через запятую / соответствие А..Г / слово)
    pattern = re.compile(
        r'(?<!\d)(\d{1,3})\s+'
        r'('
        r'(?:А\dБ\dВ\dГ\d)'  # соответствие
        r'|(?:\d(?:\s*,\s*\d)*)'  # 1, 3, 5
        r'|(?:[А-Яа-яЁёA-Za-z()«»\"\'\-]+(?:\s+[А-Яа-яЁёA-Za-z()«»\"\'\-]+){0,4})'  # текст
        r')'
        r'(?=\s+\d{1,3}\s+|$)'
    )

    for m in pattern.finditer(cleaned):
        num = int(m.group(1))
        ans = re.sub(r'\s+', ' ', m.group(2)).strip()
        ans = re.sub(r'\s*,\s*', ', ', ans)
        answers[num] = ans

    return answers


def split_task_blocks(body: str) -> list[tuple[int, str]]:
    """Разбивает текст на блоки № N. ..."""
    # Удаляем колонтитулы с номерами страниц
    body = re.sub(r'\n\s*\d+\s*\n', '\n', body)
    parts = re.split(r'(?=№\s*\d+\.)', body)
    blocks: list[tuple[int, str]] = []
    for part in parts:
        m = re.match(r'№\s*(\d+)\.\s*(.*)', part, flags=re.DOTALL)
        if not m:
            continue
        num = int(m.group(1))
        content = m.group(2).strip()
        content = re.sub(r'\n{3,}', '\n\n', content)
        blocks.append((num, content))
    return blocks


def extract_numbered_options(question: str) -> list[str]:
    """Достаёт варианты 1) ... 2) ... если они есть."""
    opts = []
    # Ищем строки вида "1) текст"
    for m in re.finditer(r'(?:^|\n)\s*(\d)\)\s*(.+?)(?=(?:\n\s*\d\)|\n\s*[АA]\.|\Z))', question, flags=re.DOTALL):
        text = re.sub(r'\s+', ' ', m.group(2)).strip().rstrip(';.,')
        if text:
            opts.append(text)
    return opts


def detect_answer_format(answer: str, question: str) -> str:
    if re.fullmatch(r'(?:\d(?:\s*,\s*\d)*)', answer):
        return 'multiple_choice'
    if re.fullmatch(r'А\dБ\dВ\dГ\d', answer, flags=re.IGNORECASE):
        return 'text'
    return 'text'


def parse_bank_pdf(path: Path) -> ParsedBankFile:
    section_name, _slug, part_name = section_from_filename(path.name)
    text = extract_pdf_text(path)
    body, answers_text = split_tasks_and_answers(text)
    answers = parse_answers(answers_text)
    blocks = split_task_blocks(body)

    tasks: list[ParsedTask] = []
    for num, content in blocks:
        answer = answers.get(num)
        if not answer:
            continue
        question = re.sub(r'\s+', ' ', content).strip()
        # сохраняем переносы чуть аккуратнее для читаемости
        question = re.sub(r'\s*(\d\))', r'\n\1', content).strip()
        question = re.sub(r'\n{3,}', '\n\n', question)
        options = extract_numbered_options(content)
        fmt = detect_answer_format(answer, content)
        tasks.append(
            ParsedTask(
                number=num,
                question=question,
                correct_answer=answer,
                answer_format=fmt,
                option_labels=options,
            )
        )

    return ParsedBankFile(
        filename=path.name,
        section_name=section_name,
        part_name=part_name,
        tasks=tasks,
    )


def parse_text_analysis_pdf(path: Path) -> ParsedBankFile:
    """Парсер для 9.1.pdf — блоки «ТЕКСТ N» + ответы «Ответы. Текст N»."""
    section_name, _slug, part_name = section_from_filename(path.name)
    text = extract_pdf_text(path)

    answer_blocks = list(
        re.finditer(
            r'(?:Ответы\.\s*Текст|Номер задания\s+Ответ)\s*(\d+)?',
            text,
            flags=re.IGNORECASE,
        )
    )
    # Собираем ответы из всех таблиц «Номер задания Ответ»
    answers_by_text: dict[int, dict[int, str]] = {}
    for m in re.finditer(
        r'(?:Ответы\.\s*Текст\s*(\d+)|Текст\s+(\d+)\s*\n\s*Номер задания)',
        text,
        flags=re.IGNORECASE,
    ):
        text_num = int(m.group(1) or m.group(2))
        chunk = text[m.end() : m.end() + 800]
        next_header = re.search(r'(?:ТЕКСТ\s+\d+|Ответы\.\s*Текст\s+\d+)', chunk, flags=re.IGNORECASE)
        if next_header:
            chunk = chunk[: next_header.start()]
        answers_by_text[text_num] = parse_answers(chunk)

    # Fallback: таблицы без явного «Ответы. Текст N» — ищем после каждого текста
    if not answers_by_text:
        for m in re.finditer(
            r'Номер задания\s+Ответ\s+((?:\d+\s+[^\n]+\s*)+)',
            text,
            flags=re.IGNORECASE,
        ):
            pass

    # Более надёжно: разбить по «ТЕКСТ N» и искать ответы в конце каждого фрагмента
    text_parts = re.split(r'(?=ТЕКСТ\s+\d+)', text)
    tasks: list[ParsedTask] = []
    global_num = 0

    for part in text_parts:
        m = re.match(r'ТЕКСТ\s+(\d+)', part.strip(), flags=re.IGNORECASE)
        if not m:
            continue
        text_num = int(m.group(1))
        # ответы в конце этого куска (после «Номер задания»)
        ans_match = re.search(r'Номер задания\s+Ответ\s*(.*)', part, flags=re.IGNORECASE | re.DOTALL)
        answers = parse_answers(ans_match.group(1)[:600]) if ans_match else answers_by_text.get(text_num, {})
        body = part[: ans_match.start()] if ans_match else part

        # вопросы вида «1. Текст...» без символа №
        q_blocks = re.split(r'(?=^\s*\d+\.\s)', body, flags=re.MULTILINE)
        for qb in q_blocks:
            qm = re.match(r'\s*(\d+)\.\s+(.*)', qb, flags=re.DOTALL)
            if not qm:
                continue
            qnum = int(qm.group(1))
            if qnum > 20:
                continue
            answer = answers.get(qnum)
            if not answer:
                continue
            content = qm.group(2).strip()
            # отрезать следующий текст «ТЕКСТ» если попал
            content = re.split(r'\nТЕКСТ\s+\d+', content)[0].strip()
            options = extract_numbered_options(content)
            global_num += 1
            fmt = detect_answer_format(answer, content)
            tasks.append(
                ParsedTask(
                    number=global_num,
                    question=f'[Текст {text_num}] {content}',
                    correct_answer=answer,
                    answer_format=fmt,
                    option_labels=options,
                )
            )

    return ParsedBankFile(
        filename=path.name,
        section_name=section_name,
        part_name=part_name,
        tasks=tasks,
    )


def parse_all_bank_pdfs(info_dir: Path) -> list[ParsedBankFile]:
    """Ищет PDF банка в папке и во вложенном open_bank/."""
    candidates: list[Path] = []
    candidates.extend(sorted(info_dir.glob('*.pdf')))
    open_bank = info_dir / 'open_bank'
    if open_bank.is_dir():
        candidates.extend(sorted(open_bank.glob('*.pdf')))

    files = []
    seen = set()
    for path in candidates:
        if path.name in seen:
            continue
        seen.add(path.name)
        key = _bank_section_key(path.stem)
        if not key:
            continue
        if key == '9.1':
            files.append(parse_text_analysis_pdf(path))
        else:
            files.append(parse_bank_pdf(path))
    return files
