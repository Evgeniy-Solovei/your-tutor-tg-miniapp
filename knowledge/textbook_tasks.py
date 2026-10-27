"""Задания школьной программы / учебника (не ЦТ/ЦЭ/РТ).

Важно: «полный текст» из PDF часто криво разложен по темам (упр. N → грубый
диапазон). Для практики и счётчиков сначала берём кураторские карточки
(«Учебник N класса…», «Школьная программа…»), дамп PDF — только запасной вариант.
"""

from __future__ import annotations

from django.db.models import Q

# Кураторские школьные задания (MCQ / программа), не OCR-страницы и не сырой PDF.
SCHOOL_CURATED_INCLUDE_Q = (
    (
        Q(source__startswith='Учебник')
        & ~Q(source__contains='полный текст')
        & ~Q(source__contains=', стр.')
    )
    | Q(source__startswith='Школьная программа')
    | Q(source__startswith='Учебник РБ')
    | Q(source__startswith='Азбука')
    | Q(source__startswith='База школы')
    | Q(source__startswith='Картинки')
)

SCHOOL_FULLTEXT_Q = Q(source__contains='полный текст')
SCHOOL_PAGE_SCAN_Q = Q(source__contains=', стр.')

SCHOOL_TEXTBOOK_EXCLUDE_Q = (
    Q(source__icontains='ЦТ OCR')
    | Q(source__icontains='ЦТ /')
    | Q(source__startswith='ЦТ ')
    | Q(source__startswith='ЦЭ ')
    | Q(source__startswith='РТ/ДРТ')
    | Q(source__startswith='Сборник изложений')
)

# Обратная совместимость: «школьный учебник» = кураторские (без сырого PDF-дампа).
SCHOOL_TEXTBOOK_INCLUDE_Q = SCHOOL_CURATED_INCLUDE_Q
SCHOOL_TEXTBOOK_SOURCE_Q = SCHOOL_CURATED_INCLUDE_Q & ~SCHOOL_TEXTBOOK_EXCLUDE_Q


def filter_school_textbook_tasks(qs):
    """Кураторские задания учебника/программы — то, что видно ученику как «Учебник»."""
    return qs.filter(SCHOOL_CURATED_INCLUDE_Q).exclude(SCHOOL_TEXTBOOK_EXCLUDE_Q)


def filter_school_fulltext_tasks(qs):
    """Сырой импорт «упр. N полный текст» — запасной пул, часто с кривой темой."""
    return qs.filter(SCHOOL_FULLTEXT_Q).exclude(SCHOOL_TEXTBOOK_EXCLUDE_Q)


def filter_school_page_scan_tasks(qs):
    """Страницы 1 класса с картинкой."""
    return qs.filter(SCHOOL_PAGE_SCAN_Q).exclude(SCHOOL_TEXTBOOK_EXCLUDE_Q)


def prefer_school_tasks(qs):
    """Синхронный выбор: куратор → страница → полный текст → как есть (без ЦТ)."""
    base = qs.exclude(SCHOOL_TEXTBOOK_EXCLUDE_Q)
    curated = filter_school_textbook_tasks(base)
    if curated.exists():
        return curated
    pages = filter_school_page_scan_tasks(base)
    if pages.exists():
        return pages
    full = filter_school_fulltext_tasks(base)
    if full.exists():
        return full
    return base
