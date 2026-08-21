"""Парсер «Русский язык. ЦТ. Тренажёр» (Долбик и др., Аверсэв)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from knowledge.pdf_parser import ParsedTask, extract_numbered_options

ROMAN = r'[IVXLC]+'
# ответы: multi-select, соответствие А/Б/В, буквы, короткие слова, длинный текст
ANS_BODY = (
    # З/б допускаем: PDF пишет БЗ вместо Б3, Гб вместо Г6
    r'(?:[АA]\s*[-—]?\s*[\dЗзбБBВVГGДD,;\s\-—]+(?:[;,]?\s*[БBВVГGДD]\s*[-—]?\s*[\dЗзб,;\s\-—]+)*)'
    r'|(?:\d\s*[-—]\s*[^.]{2,160}(?:;\s*\d[\d,\s]*\s*[-—]\s*[^.]{2,100})*)'
    r'|(?:\d-\s*[\d,\s]+(?:;\s*\d-\s*[\d,\s]+)*)'
    r'|(?:\d(?:\s*,\s*\d)*)'
    r'|(?:[«\"].{5,400}?[»\"])'
    r'|(?:[а-яёa-z][а-яёa-z\-]*(?:\s*[,;—\-]\s*[а-яёa-z0-9][а-яёa-z0-9\-,\s«»\"]*)*)'
)
ANS_ITEM = re.compile(
    # PDF часто без пробела после точки: «2.2,4.» / «7.3.»
    rf'(\d{{1,2}})\.\s*({ANS_BODY})\.?(?=\s+\d{{1,2}}\.\s*|\s*$|\n)',
    re.I,
)
QUESTION_START = re.compile(r'(?:^|\n)\s*(\d{1,2})\.\s+')
CODE_Q = re.compile(r'(?:^|\n)\s*([АAВB]\d{1,2})\.\s+', re.I)
CODE_ANS = re.compile(
    rf'([АAВB]\d{{1,2}})\.\s*({ANS_BODY})\.?(?=\s+[АAВB]\d{{1,2}}\.\s*|\s*$|\n)',
    re.I,
)
TEST_HDR = re.compile(r'(?:^|\n)Тест\s+(\d+)\s*(?=\n|$)')
ROMAN_HDR = re.compile(rf'(?:^|\n)({ROMAN})\s*(?=\n|$)')
ROMAN_TITLED = re.compile(rf'(?:^|\n)({ROMAN})\.\s+([^\n]+)')
VARIANT_HDR = re.compile(r'(?:^|\n)Вариант\s+([IVXLC\d]+)\s*(?=\n|$)', re.I)
POS_HDR = re.compile(
    r'(?:^|\n)(Имя существительное|Имя прилагательное|Имя числительное|'
    r'Местоимение|Глагол|Причастие\.?\s*Деепричастие|Наречие|'
    r'Предлог|Союз|Частица|Междометие)\s*(?=\n|$)',
    re.I,
)
NEXT_SECTION = re.compile(
    r'\n(?:'
    r'ФОНЕТИКА|ЛЕКСИКА|СЛОВООБРАЗОВАНИЕ|МОРФОЛОГИЯ|СИНТАКСИС|'
    r'ПУНКТУАЦИЯ|КУЛЬТУРА РЕЧИ|ТЕКСТ|СТИЛИ РЕЧИ|КОНТРОЛЬН|'
    r'ОБОБЩАЮЩИЕ|ТРЕНИРОВОЧНЫЕ ТЕСТЫ|Помогаем учить|Содержание книги'
    r')',
)
SECTION_MARKERS = {
    'ОРФОГРАФИЯ': 'Орфография',
    'ПУНКТУАЦИЯ': 'Пунктуация',
    'ЛЕКСИКА': 'Лексика',
    'ФОНЕТИКА': 'Фонетика',
    'МОРФОЛОГИЯ': 'Морфология',
    'СИНТАКСИС': 'Синтаксис',
    'СЛОВООБРАЗОВ': 'Словообразование',
    'КУЛЬТУРА РЕЧИ': 'Культура речи',
    'ОБОБЩАЮЩИЕ': 'Обобщающие тесты',
    'КОНТРОЛЬН': 'Контрольные тесты',
    'ТЕКСТ': 'Текст',
    'СОСТАВ СЛОВА': 'Состав слова',
    'СТИЛИ РЕЧИ': 'Стили речи',
}


@dataclass
class ParsedTrenazher:
    filename: str
    tasks: list[ParsedTask] = field(default_factory=list)


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    text = '\n'.join((page.extract_text() or '') for page in reader.pages)
    text = text.replace('\u00a0', ' ').replace('\xad', '')
    text = re.sub(r'[ \t]+', ' ', text)
    return _normalize_pdf_ocr(text)


def _normalize_pdf_ocr(text: str) -> str:
    """PDF путает 3↔З, 6↔б, 10↔Ю, 11↔Н/All, 30↔ЗО в кодах А/В/Б/Г."""
    # убрать «Часть А/В» между кодами ответов
    text = re.sub(r'\nЧасть\s*[АABВB]\s*\n', '\n', text, flags=re.I)
    repl = [
        (r'(?:^|[\n\s])АЗО\.', '\nА30.'),
        (r'(?:^|[\n\s])А2б\.', '\nА26.'),
        (r'(?:^|[\n\s])АЮ\.', '\nА10.'),
        (r'(?:^|[\n\s])АН\.', '\nА11.'),
        (r'(?:^|[\n\s])All\.', '\nА11.'),
        (r'(?:^|[\n\s])Ail\.', '\nА11.'),
        (r'(?:^|[\n\s])AI1\.', '\nА11.'),
        (r'(?:^|[\n\s])Аб\.', '\nА6.'),
        (r'(?:^|[\n\s])АЗ\.', '\nА3.'),
        (r'(?:^|[\n\s])Вб\.', '\nВ6.'),
        (r'(?:^|[\n\s])ВЗ\.', '\nВ3.'),
        (r'(?:^|[\n\s])ВЮ\.', '\nВ10.'),
        # Latin B instead of Cyrillic В
        (r'(?:^|[\n\s])Bl\.', '\nВ1.'),
        (r'(?:^|[\n\s])B(\d+)\.', r'\nВ\1.'),
    ]
    for pat, rep in repl:
        text = re.sub(pat, rep, text)
    # внутри ключей соответствия: БЗ→Б3, ГЗ→Г3, Гб→Г6
    text = re.sub(r'([АAБBВVГGДD])\s*З\b', r'\g<1>3', text)
    text = re.sub(r'([АAБBВVГGДD])\s*б\b', r'\g<1>6', text)
    # А25.2.5. → А25. 2, 5. (точка вместо запятой в ключе)
    text = re.sub(
        r'([АAВB]\d{1,2})\.(\d)[.,](\d)(?!\d)',
        r'\1. \2, \3',
        text,
    )
    return text


def _guess_section(text: str) -> str:
    # заголовок раздела — в первых строках; «контрольных тестов» в аннотации не считаем
    head = text[:2000]
    # явные заголовки с новой строки
    header_re = re.compile(
        r'(?:^|\n)\s*(ОРФОГРАФИЯ|ФОНЕТИКА|ЛЕКСИКА|СЛОВООБРАЗОВАНИЕ|МОРФОЛОГИЯ|'
        r'СИНТАКСИС(?:\s+И\s+ПУНКТУАЦИЯ)?|ПУНКТУАЦИЯ|КУЛЬТУРА РЕЧИ|'
        r'ТЕКСТ(?!\w)|СТИЛИ РЕЧИ|ОБОБЩАЮЩИЕ ТЕСТОВЫЕ|КОНТРОЛЬНЫЕ ТЕСТЫ)'
        r'(?:\s*$|\s*\n)',
        re.I | re.M,
    )
    m = header_re.search(head)
    if m:
        raw = m.group(1).upper()
        for k, title in SECTION_MARKERS.items():
            if raw.startswith(k):
                return title
    upper = head.upper()
    best_pos, best = 10**9, 'Тренажёр ЦТ'
    for k, title in SECTION_MARKERS.items():
        if k in ('КОНТРОЛЬН', 'ОБОБЩАЮЩИЕ'):
            continue
        pos = upper.find(k)
        if 0 <= pos < best_pos:
            best_pos, best = pos, title
    return best


def _clean_answer(raw: str) -> str:
    ans = raw.replace('—', '-').replace('–', '-')
    ans = re.sub(r'\s+', ' ', ans).strip().rstrip('.;')
    # БЗ / ВЗ → Б3 / В3 (PDF часто путает 3 и З)
    ans = re.sub(r'([АAБBВVГGДD])\s*З\b', r'\g<1>3', ans, flags=re.I)
    ans = re.sub(r'\s*,\s*', ', ', ans)
    ans = re.sub(r'\s*;\s*', '; ', ans)
    return ans


def _answers_in_chunk(chunk: str) -> dict[int, str]:
    chunk = re.sub(r'\n©[^\n]+\n', '\n', chunk)
    chunk = re.sub(r'\n\d{1,3}\n', '\n', chunk)
    text = re.sub(r'\s+', ' ', chunk.strip())
    out: dict[int, str] = {}
    for m in ANS_ITEM.finditer(text):
        num = int(m.group(1))
        if num > 10:
            continue
        ans = _clean_answer(m.group(2))
        if re.fullmatch(rf'{ROMAN}', ans, re.I):
            continue
        if ans.upper() in {'ТЕСТ'}:
            continue
        out[num] = ans
    return out


def _cut_answers_and_questions(block: str) -> tuple[str, str]:
    """В блоке «Ответы…» ключи идут первыми, затем следующий раздел заданий."""
    body = re.sub(r'^\n?Ответы\n', '', block)
    cut = NEXT_SECTION.search(body)
    if cut and cut.start() > 40:
        return body[: cut.start()], body[cut.start() :]
    # копирайт mid-answers — режем только если дальше явный заголовок раздела
    for m in re.finditer(r'\n©[^\n]+\n', body):
        tail = body[m.end() : m.end() + 120]
        if NEXT_SECTION.match('\n' + tail.lstrip('\n')) or re.match(
            r'\s*(?:ОБОБЩАЮЩИЕ|КОНТРОЛЬН|Вариант\s)',
            tail,
        ):
            return body[: m.start()], body[m.end() :]
    return body, ''


def _short_pos(name: str) -> str:
    name = re.sub(r'\s+', ' ', name).strip()
    mapping = {
        'Имя существительное': 'сущ',
        'Имя прилагательное': 'прил',
        'Имя числительное': 'числ',
        'Местоимение': 'мест',
        'Глагол': 'глаг',
        'Наречие': 'нар',
        'Предлог': 'предл',
        'Союз': 'союз',
        'Частица': 'част',
        'Междометие': 'межд',
    }
    for k, v in mapping.items():
        if name.lower().startswith(k.lower()):
            return v
    if 'причастие' in name.lower():
        return 'прич'
    return name[:12]


def _parse_twocol_answers(chunk: str) -> dict[int, str]:
    """Двухколоночные ключи: «1. 1,2,4. 3. 1,2,3,4.» на одной строке."""
    out: dict[int, str] = {}
    for line in chunk.splitlines():
        line = line.strip()
        if not line or line.startswith('©') or re.fullmatch(r'\d{1,3}', line):
            continue
        if POS_HDR.match('\n' + line) or VARIANT_HDR.match('\n' + line):
            break
        if re.match(rf'^{ROMAN}\s*$', line) or line.startswith('Тест'):
            break
        items = list(ANS_ITEM.finditer(re.sub(r'\s+', ' ', line)))
        for m in items:
            num = int(m.group(1))
            if 1 <= num <= 10:
                out[num] = _clean_answer(m.group(2))
    return out


def _parse_multicolumn_tests(chunk: str) -> dict[str, dict[int, str]]:
    """Строки вида «1. 1,3,4. 1.2,3,4. 1. 1,3.» → Тест1/2/3."""
    hdr = re.search(r'Тест\s+1\s+Тест\s+2\s+Тест\s+3', chunk)
    if not hdr:
        return {}
    rest = chunk[hdr.end() :]
    by_test: dict[str, dict[int, str]] = {
        'Тест1': {},
        'Тест2': {},
        'Тест3': {},
    }
    for line in rest.splitlines():
        line = line.strip()
        if not line or line.startswith('©') or re.fullmatch(r'\d{1,3}', line):
            continue
        if re.match(rf'^{ROMAN}\s*$', line) or line.startswith('Тест'):
            break
        items = list(ANS_ITEM.finditer(re.sub(r'\s+', ' ', line)))
        if len(items) < 2:
            continue
        for idx, m in enumerate(items[:3]):
            num = int(m.group(1))
            if num > 10:
                continue
            key = f'Тест{idx + 1}'
            by_test[key][num] = _clean_answer(m.group(2))
    return {k: v for k, v in by_test.items() if v}


def _normalize_roman_glitch(text: str) -> str:
    # PDF: Ill / IIl → III
    text = re.sub(r'(?:^|\n)I[lI]{2}\s*\n', '\nIII\n', text)
    text = re.sub(r'(?:^|\n)Il\s*\n', '\nII\n', text)
    return text


def _ingest_pos_subsections(units: dict, roman: str, body: str) -> bool:
    parts = re.split(
        r'(?:^|\n)(Имя существительное|Имя прилагательное|Имя числительное|'
        r'Местоимение|Глагол|Причастие\.?\s*Деепричастие|Наречие|'
        r'Предлог|Союз|Частица|Междометие)\s*\n',
        body,
        flags=re.I,
    )
    if len(parts) < 3:
        return False
    i = 1
    while i + 1 < len(parts):
        pos = _short_pos(parts[i])
        amap = _parse_twocol_answers(parts[i + 1])
        if not amap:
            amap = _answers_in_chunk(parts[i + 1])
        if amap:
            units[f'{roman}/{pos}'] = amap
        i += 2
    return True


def _ingest_roman_body(units: dict, roman: str, body: str) -> None:
    multi = _parse_multicolumn_tests(body)
    if multi:
        for tname, amap in multi.items():
            units[f'{roman}/{tname}'] = amap
        return
    if _ingest_pos_subsections(units, roman, body):
        # хвост после POS может содержать Тест N (III культуры речи)
        pass
    test_parts = re.split(r'(?:^|\n)Тест\s+(\d+)\s*\n', body)
    if len(test_parts) > 1:
        j = 1
        while j + 1 < len(test_parts):
            tnum = test_parts[j]
            tbody = test_parts[j + 1]
            amap = _answers_in_chunk(tbody)
            if amap:
                units[f'{roman}/Тест{tnum}'] = amap
            j += 2
        if any(k.startswith(f'{roman}/') for k in units):
            return
    if any(k.startswith(f'{roman}/') for k in units):
        return
    amap = _answers_in_chunk(body)
    if amap:
        units[roman] = amap


def _split_variant_answers(ans_text: str) -> dict[str, dict[int, str]]:
    units: dict[str, dict[int, str]] = {}
    parts = re.split(r'(?:^|\n)Вариант\s+([IVXLC\d]+)\s*\n', ans_text, flags=re.I)
    if len(parts) < 3:
        return units
    i = 1
    while i + 1 < len(parts):
        var = parts[i].strip().upper()
        body = parts[i + 1]
        amap = _answers_in_chunk(body)
        if amap:
            units[f'Вариант{var}'] = amap
        i += 2
    return units


def _split_code_answers(ans_text: str) -> dict[str, dict[str, str]]:
    """Контрольные: А1. 1,2,4. → {'Вариант1': {'А1': '1, 2, 4', ...}}"""
    units: dict[str, dict[str, str]] = {}
    # нормализация OCR: Аб→А6, АЮ→А10, АН→А11, АЗ→А3
    text = ans_text
    text = re.sub(r'\bАб\b', 'А6', text)
    text = re.sub(r'\bАЮ\b', 'А10', text)
    text = re.sub(r'\bАН\b', 'А11', text)
    text = re.sub(r'\bАЗ\b', 'А3', text)
    text = re.sub(r'\bВб\b', 'В6', text)
    parts = re.split(r'(?:^|\n)Вариант\s+(\d+)\s*\n', text, flags=re.I)
    if len(parts) < 3:
        # иногда «Вариант 1» уже был, весь блок — один вариант
        flat = {}
        for m in CODE_ANS.finditer(re.sub(r'\s+', ' ', text)):
            code = m.group(1).upper().replace('A', 'А').replace('B', 'В')
            flat[code] = _clean_answer(m.group(2))
        if flat:
            units['Вариант1'] = flat
        return units
    i = 1
    while i + 1 < len(parts):
        var = parts[i].strip()
        body = parts[i + 1]
        flat = {}
        for m in CODE_ANS.finditer(re.sub(r'\s+', ' ', body)):
            code = m.group(1).upper().replace('A', 'А').replace('B', 'В')
            flat[code] = _clean_answer(m.group(2))
        if flat:
            units[f'Вариант{var}'] = flat
        i += 2
    return units


def _split_answer_units(ans_text: str) -> dict[str, dict]:
    """
    Ключи секций:
      I / II / … / Тест1 / I/Тест1 / II/сущ / ВариантI / Вариант1(код А1)
    """
    units: dict[str, dict] = {}
    ans_text = _normalize_roman_glitch(ans_text)

    # контрольные А1/В1
    if re.search(r'(?:^|\n)А\d{1,2}\.', ans_text) or re.search(r'Часть\s*А', ans_text):
        code_units = _split_code_answers(ans_text)
        if code_units:
            return code_units

    # обобщающие Вариант I/II
    if re.search(r'(?:^|\n)Вариант\s+[IVXLC]', ans_text, re.I):
        var_units = _split_variant_answers(ans_text)
        if var_units:
            return var_units

    # ведущий multi-column без «I»
    if re.match(r'\s*Тест\s+1\s+Тест\s+2\s+Тест\s+3', ans_text):
        m = re.search(rf'\n({ROMAN})\s*\n', ans_text)
        head = ans_text[: m.start()] if m else ans_text
        multi = _parse_multicolumn_tests(head)
        for tname, amap in multi.items():
            units[f'I/{tname}'] = amap
        if m:
            ans_text = ans_text[m.start() :]
        else:
            return units

    roman_parts = re.split(rf'(?:^|\n)({ROMAN})\s*\n', ans_text)
    if len(roman_parts) > 1:
        i = 1
        while i + 1 < len(roman_parts):
            roman = roman_parts[i].strip()
            body = roman_parts[i + 1]
            _ingest_roman_body(units, roman, body)
            i += 2
        return units

    test_parts = re.split(r'(?:^|\n)Тест\s+(\d+)\s*\n', ans_text)
    if len(test_parts) > 1:
        j = 1
        while j + 1 < len(test_parts):
            tnum = test_parts[j]
            tbody = test_parts[j + 1]
            tbody = NEXT_SECTION.split(tbody, maxsplit=1)[0] if NEXT_SECTION.search(tbody) and NEXT_SECTION.search(tbody).start() > 20 else tbody
            amap = _answers_in_chunk(tbody)
            if amap:
                units[f'Тест{tnum}'] = amap
            j += 2
        return units

    multi = _parse_multicolumn_tests(ans_text)
    if multi:
        return {f'I/{k}' if not k.startswith('I') else k: v for k, v in multi.items()}

    amap = _answers_in_chunk(ans_text)
    if amap:
        units[''] = amap
    return units


def _trim_next_section(body: str) -> str:
    m = NEXT_SECTION.search(body)
    if m and m.start() > 20:
        return body[: m.start()]
    return body


def _questions_in_body(body: str) -> dict[int, tuple[str, list[str]]]:
    body = _trim_next_section(body)
    matches = list(QUESTION_START.finditer(body))
    out: dict[int, tuple[str, list[str]]] = {}
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if num > 10:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[start:end].strip()
        chunk = re.split(r'\n(?:Тест\s+\d+|[IVXLC]+\.\s|Вариант\s+|Имя\s)', chunk)[0]
        chunk = re.sub(r'\n©[^\n]+', '\n', chunk)
        chunk = re.sub(r'\n\d{1,3}(?=\n)', '\n', chunk)
        opts = extract_numbered_options(chunk)
        if len(opts) < 2:
            opts = []
            for om in re.finditer(
                r'(?:^|\n)\s*(\d)\)\s*([^\n]+(?:\n(?!\s*\d\))[^\n]+)*)',
                chunk,
            ):
                opts.append(re.sub(r'\s+', ' ', om.group(2)).strip().rstrip(';.,')[:490])
        stem = re.split(r'\n\s*\d\)', chunk, maxsplit=1)[0]
        stem = re.sub(r'\s+', ' ', stem).strip()
        if len(stem) < 5 and not opts:
            continue
        out[num] = (stem[:1500], opts)
    return out


def _questions_by_code(body: str) -> dict[str, tuple[str, list[str]]]:
    body = _trim_next_section(body)
    matches = list(CODE_Q.finditer(body))
    out: dict[str, tuple[str, list[str]]] = {}
    for i, m in enumerate(matches):
        code = m.group(1).upper().replace('A', 'А').replace('B', 'В')
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[start:end].strip()
        chunk = re.split(r'\n(?:Вариант\s+|Часть\s)', chunk)[0]
        opts = extract_numbered_options(chunk)
        if len(opts) < 2:
            opts = []
            for om in re.finditer(
                r'(?:^|\n)\s*(\d)\)\s*([^\n]+(?:\n(?!\s*\d\))[^\n]+)*)',
                chunk,
            ):
                opts.append(re.sub(r'\s+', ' ', om.group(2)).strip().rstrip(';.,')[:490])
        stem = re.split(r'\n\s*\d\)', chunk, maxsplit=1)[0]
        stem = re.sub(r'\s+', ' ', stem).strip()
        if len(stem) < 5 and not opts:
            continue
        out[code] = (stem[:1500], opts)
    return out


def _split_question_units(q_text: str) -> dict[str, tuple[str, dict]]:
    """Те же ключи, что у _split_answer_units."""
    units: dict[str, tuple[str, dict]] = {}
    q_text = q_text or ''

    # контрольные: Вариант N + А1/В1
    if re.search(r'(?:^|\n)А\d{1,2}\.', q_text) or re.search(r'Часть\s*А', q_text):
        vparts = re.split(r'(?:^|\n)Вариант\s+(\d+)\s*\n', q_text, flags=re.I)
        if len(vparts) > 1:
            j = 1
            while j + 1 < len(vparts):
                var = vparts[j].strip()
                body = vparts[j + 1]
                cmap = _questions_by_code(body)
                if cmap:
                    units[f'Вариант{var}'] = (f'Вариант {var}', cmap)
                j += 2
            if units:
                return units
        cmap = _questions_by_code(q_text)
        if cmap:
            units['Вариант1'] = ('Вариант 1', cmap)
            return units

    # обобщающие Вариант I
    if re.search(r'(?:^|\n)Вариант\s+[IVXLC]', q_text, re.I):
        vparts = re.split(r'(?:^|\n)Вариант\s+([IVXLC\d]+)\s*\n', q_text, flags=re.I)
        if len(vparts) > 1:
            j = 1
            while j + 1 < len(vparts):
                var = vparts[j].strip().upper()
                body = vparts[j + 1]
                qmap = _questions_in_body(body)
                if qmap:
                    units[f'Вариант{var}'] = (f'Вариант {var}', qmap)
                j += 2
            if units:
                return units

    # I. Title … with optional nested Тест / POS
    titled = list(ROMAN_TITLED.finditer(q_text))
    if titled:
        for idx, m in enumerate(titled):
            roman = m.group(1).strip()
            title = re.sub(r'\s+', ' ', m.group(2)).strip()
            start = m.end()
            end = titled[idx + 1].start() if idx + 1 < len(titled) else len(q_text)
            body = _trim_next_section(q_text[start:end])
            # POS subsections
            pos_parts = re.split(
                r'(?:^|\n)(Имя существительное|Имя прилагательное|Имя числительное|'
                r'Местоимение|Глагол|Причастие\.?\s*Деепричастие|Наречие|'
                r'Предлог|Союз|Частица|Междометие)\s*\n',
                body,
                flags=re.I,
            )
            if len(pos_parts) > 1:
                j = 1
                while j + 1 < len(pos_parts):
                    pos = _short_pos(pos_parts[j])
                    qmap = _questions_in_body(pos_parts[j + 1])
                    if qmap:
                        units[f'{roman}/{pos}'] = (f'{title} · {pos_parts[j].strip()}', qmap)
                    j += 2
            test_parts = re.split(r'(?:^|\n)Тест\s+(\d+)\s*\n', body)
            if len(test_parts) > 1:
                j = 1
                while j + 1 < len(test_parts):
                    tnum = test_parts[j]
                    tbody = test_parts[j + 1]
                    qmap = _questions_in_body(tbody)
                    if qmap:
                        units[f'{roman}/Тест{tnum}'] = (f'{title} · Тест {tnum}', qmap)
                    j += 2
            elif not any(k.startswith(f'{roman}/') for k in units):
                qmap = _questions_in_body(body)
                if qmap:
                    units[roman] = (title, qmap)
        if units:
            return units

    test_parts = re.split(r'(?:^|\n)Тест\s+(\d+)\s*\n', q_text)
    if len(test_parts) > 1:
        j = 1
        while j + 1 < len(test_parts):
            tnum = test_parts[j]
            tbody = test_parts[j + 1]
            qmap = _questions_in_body(tbody)
            if qmap:
                units[f'Тест{tnum}'] = (f'Тест {tnum}', qmap)
            j += 2
        if units:
            return units

    roman_parts = re.split(rf'(?:^|\n)({ROMAN})\s*\n', q_text)
    if len(roman_parts) > 1:
        i = 1
        while i + 1 < len(roman_parts):
            roman = roman_parts[i].strip()
            body = roman_parts[i + 1]
            qmap = _questions_in_body(body)
            if qmap:
                units[roman] = (roman, qmap)
            i += 2
        if units:
            return units

    qmap = _questions_in_body(q_text)
    if qmap:
        units[''] = ('', qmap)
    return units


def _build_task(
    section: str,
    unit_key: str,
    title: str,
    num_or_code,
    stem: str,
    opts: list[str],
    answer: str,
) -> ParsedTask | None:
    if re.fullmatch(rf'{ROMAN}', answer, re.I):
        return None
    # копирайт в коротком «стеме» = мусор; в длинном тексте задания — ок (сноска на странице)
    if len(stem) < 60 and ('Аверсэв' in stem or 'ОДО «' in stem):
        return None
    if len(stem) < 8:
        return None
    if answer.upper() in {'AL', 'AI', 'АL', 'ТЕСТ'}:
        return None
    # «1, 2, И» и подобный OCR-мусор в обобщающих
    if re.search(r',\s*И\b', answer, re.I) and not re.search(r'\d', answer.split(',')[-1]):
        answer = re.sub(r',\s*И\b', '', answer, flags=re.I).strip(' ,')
    if not answer or len(answer) < 1:
        return None
    compact = answer.replace(' ', '')
    need_mc = bool(re.fullmatch(r'(?:\d(?:,\d)*)', compact))
    if re.search(r'[АA]\s*[-—]?\s*\d', answer, re.I):
        need_mc = False
    # одиночная римская в ответе — мусор
    if need_mc is False and re.fullmatch(rf'{ROMAN}', compact, re.I):
        return None
    fmt = 'multiple_choice' if need_mc and len(opts) >= 2 else 'text'
    if fmt == 'multiple_choice':
        digits = [int(x.strip()) for x in answer.split(',') if x.strip().isdigit()]
        if not digits:
            fmt = 'text'
        else:
            max_opt = max(digits)
            while len(opts) < max_opt:
                opts.append(f'(вариант {len(opts) + 1})')
            opts = [o[:490] for o in opts]
    if fmt == 'text' and opts:
        stem = stem + '\n' + '\n'.join(f'{j}) {o}' for j, o in enumerate(opts, 1))
        opts = []
    if title:
        tag = f'{section} · {title}'
    elif unit_key:
        tag = f'{section} · {unit_key}'
    else:
        tag = section
    label = num_or_code if isinstance(num_or_code, str) else f'№{num_or_code}'
    if isinstance(num_or_code, str):
        qtext = f'[{tag} · {label}] {stem}'
    else:
        qtext = f'[{tag} · {label}] {stem}'
    return ParsedTask(
        number=0,
        question=qtext[:4000],
        correct_answer=answer,
        answer_format=fmt,
        option_labels=opts,
    )


def _unit_sort_key(key: str) -> tuple:
    if not key:
        return (0, 0, '')
    if key.startswith('Вариант'):
        rest = key.replace('Вариант', '')
        if rest.isdigit():
            return (100, int(rest), key)
        return (90, _roman_value(rest), key)
    roman, test = key, 0
    if '/' in key:
        roman, tpart = key.split('/', 1)
        m = re.search(r'(\d+)', tpart)
        test = int(m.group(1)) if m else hash(tpart) % 100
    elif key.startswith('Тест'):
        m = re.search(r'(\d+)', key)
        return (0, int(m.group(1)) if m else 0, key)
    return (_roman_value(roman), test, key)


def _roman_value(roman: str) -> int:
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
    if not roman:
        return 0
    total, prev = 0, 0
    for ch in reversed(roman.upper()):
        v = vals.get(ch, 0)
        total += v if v >= prev else -v
        prev = v
    return total


def parse_aversev_trenazher(
    path: Path,
    *,
    answer_block: int | None = None,
    roman_from: str | None = None,
    roman_to: str | None = None,
) -> ParsedTrenazher:
    """
    Структура PDF:
      [вопросы раздела A]
      Ответы
      [ключи A]
      [вопросы раздела B]
      Ответы
      [ключи B]
      …
    """
    text = extract_text(path)
    parts = re.split(r'(?=\nОтветы\n)', text)
    tasks: list[ParsedTask] = []
    global_n = 0
    block_idx = 0
    pending_questions = ''

    for i, part in enumerate(parts):
        if not re.match(r'\n?Ответы\n', part):
            if i == 0:
                pending_questions = part
            continue

        block_idx += 1
        ans_text, next_q = _cut_answers_and_questions(part)
        q_text = pending_questions
        pending_questions = next_q

        if answer_block is not None and block_idx != answer_block:
            continue

        section = _guess_section(q_text) if q_text.strip() else _guess_section(ans_text)
        q_units = _split_question_units(q_text)
        a_units = _split_answer_units(ans_text)

        keys = sorted(set(q_units) & set(a_units), key=_unit_sort_key)
        for unit_key in keys:
            if roman_from or roman_to:
                roman = unit_key.split('/')[0] if unit_key else ''
                if roman.startswith('Вариант'):
                    roman = ''
                if roman_from and _roman_value(roman) < _roman_value(roman_from):
                    continue
                if roman_to and _roman_value(roman) > _roman_value(roman_to):
                    continue
            title, questions = q_units[unit_key]
            answers = a_units[unit_key]
            for key in sorted(set(questions) & set(answers), key=lambda x: (isinstance(x, str), str(x))):
                stem, opts = questions[key]
                parsed = _build_task(
                    section, unit_key, title, key, stem, list(opts), answers[key]
                )
                if not parsed:
                    continue
                global_n += 1
                parsed.number = global_n
                tasks.append(parsed)

    return ParsedTrenazher(filename=path.name, tasks=tasks)
