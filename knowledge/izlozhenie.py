"""Формат заданий-изложений и разбор текста вопроса."""
from __future__ import annotations

import re
from dataclasses import dataclass


MARKER_START = '<<<ТЕКСТ'
MARKER_END = 'ТЕКСТ>>>'


@dataclass
class IzlozheniePayload:
    title: str
    word_count: int | None
    instruction: str
    body: str
    raw_question: str

    @property
    def is_izlozhenie(self) -> bool:
        return bool(self.body)


def build_izlozhenie_question(title: str, word_count: int, body: str) -> str:
    return (
        f'ИЗЛОЖЕНИЕ\n'
        f'Заголовок: {title}\n'
        f'Объём исходного текста: ~{word_count} слов\n\n'
        f'Задание: прочитай текст и напиши подробное изложение. '
        f'Передай содержание своими словами, сохрани стиль и ключевые факты. '
        f'Проверь орфографию и пунктуацию.\n\n'
        f'{MARKER_START}\n'
        f'{body}\n'
        f'{MARKER_END}'
    )


def parse_izlozhenie_question(question: str) -> IzlozheniePayload:
    raw = question or ''
    title = ''
    word_count = None
    instruction = ''
    body = ''

    m_title = re.search(r'(?m)^Заголовок:\s*(.+)\s*$', raw)
    if m_title:
        title = m_title.group(1).strip()
    else:
        m_old = re.search(r'Изложение:\s*«(.+?)»', raw)
        if m_old:
            title = m_old.group(1).strip()

    m_wc = re.search(r'~?(\d+)\s*слов', raw)
    if m_wc:
        word_count = int(m_wc.group(1))

    if MARKER_START in raw and MARKER_END in raw:
        start = raw.index(MARKER_START) + len(MARKER_START)
        end = raw.index(MARKER_END)
        body = raw[start:end].strip().lstrip('\n')
        before = raw[: raw.index(MARKER_START)].strip()
        m_instr = re.search(r'Задание:\s*(.+)', before, flags=re.S)
        instruction = (m_instr.group(1).strip() if m_instr else before)
    else:
        # старый формат с ———
        m_old_body = re.search(r'———\s*(.*?)\s*———', raw, flags=re.S)
        if m_old_body:
            body = m_old_body.group(1).strip()
        instruction = 'Прочитай текст и напиши подробное изложение.'

    return IzlozheniePayload(
        title=title or 'Изложение',
        word_count=word_count,
        instruction=instruction or 'Напиши подробное изложение.',
        body=body,
        raw_question=raw,
    )


def task_payload_for_api(task, *, topic_name: str | None = None) -> dict:
    """Сериализация задания для Mini App (изложение — удобные поля)."""
    parsed = parse_izlozhenie_question(task.question)
    if topic_name is None:
        # Только из cache (select_related) — без синхронного запроса в async.
        cached = task._state.fields_cache.get('topic')
        topic_name = cached.name if cached is not None else ''

    image_url = ''
    try:
        if getattr(task, 'image', None) and task.image:
            image_url = task.image.url
    except ValueError:
        image_url = ''

    reading_text = getattr(task, 'reading_text', '') or ''

    base = {
        'question': task.question,
        'answer_format': task.answer_format,
        'topic_name': topic_name or '',
        'image_url': image_url,
        'reading_text': reading_text,
        'is_izlozhenie': bool(parsed.body and task.answer_format == 'text'),
        'is_primary': bool(image_url) or (getattr(task, 'source', '') or '').startswith('Картинки'),
    }
    if base['is_izlozhenie']:
        base.update(
            {
                'title': parsed.title,
                'word_count': parsed.word_count,
                'instruction': parsed.instruction,
                'stimulus_text': parsed.body,
            }
        )
    return base
