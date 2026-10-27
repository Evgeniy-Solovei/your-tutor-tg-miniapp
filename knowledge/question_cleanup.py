"""Убирает из текста задания служебные номера страниц/упражнений.

Номер остаётся в source (для импорта/админки), ученику в question он не нужен.
"""

from __future__ import annotations

import re

# «Упражнение 210 (учебник 2 класса, часть 2)» / «Упражнение 35.8 (Учебник 11 кл.)»
_EXERCISE_HEADER = re.compile(
    r'^Упражнение\s+[\d.]+\s*\([^)\n]*\)\s*\n*',
    re.IGNORECASE,
)

_TEXT_LABEL = re.compile(r'^Текст упражнения:\s*\n*', re.IGNORECASE)

# «(стр. 36)» в любом месте вопроса
_PAGE_PAREN = re.compile(r'\s*\(стр\.\s*\d+\)', re.IGNORECASE)

# Старые формулировки страниц 1 класса
_PAGE_LEAD = re.compile(
    r'^Страница\s+\d+\s+учебника[^\n]*\n+(?:Раздел:[^\n]*\n+)?',
    re.IGNORECASE,
)

_LOOK_AT_PAGE = re.compile(
    r'Посмотри на картинку страницы учебника\s*\(стр\.\s*\d+\)\.',
    re.IGNORECASE,
)


def clean_student_question(question: str) -> str:
    """Возвращает формулировку без номеров упр./стр. для показа ученику."""
    if not question:
        return question
    q = question.replace('\r\n', '\n').strip()
    q = _EXERCISE_HEADER.sub('', q)
    q = _TEXT_LABEL.sub('', q)
    q = _PAGE_LEAD.sub('', q)
    q = _PAGE_PAREN.sub('', q)
    q = _LOOK_AT_PAGE.sub('Посмотри на картинку страницы учебника.', q)
    # лишние пустые строки после вырезания шапки
    q = re.sub(r'\n{3,}', '\n\n', q).strip()
    return q
