"""Задания школьной программы / учебника (не ЦТ/ЦЭ/РТ)."""

from __future__ import annotations

from django.db.models import Q

# Всё, что импортировано как школьный учебник / программа.
# Включая страницы 1 класса с картинкой («…, стр. N») — это задания «смотри и ответь».
SCHOOL_TEXTBOOK_INCLUDE_Q = (
    Q(source__contains='полный текст')
    | Q(source__startswith='Учебник')
    | Q(source__startswith='Школьная программа')
    | Q(source__startswith='Азбука')
    | Q(source__startswith='База школы')
)

SCHOOL_TEXTBOOK_EXCLUDE_Q = (
    Q(source__icontains='ЦТ OCR')
    | Q(source__icontains='ЦТ /')
    | Q(source__startswith='ЦТ ')
    | Q(source__startswith='ЦЭ ')
    | Q(source__startswith='РТ/ДРТ')
    | Q(source__startswith='Сборник изложений')
)

SCHOOL_TEXTBOOK_SOURCE_Q = SCHOOL_TEXTBOOK_INCLUDE_Q & ~SCHOOL_TEXTBOOK_EXCLUDE_Q


def filter_school_textbook_tasks(qs):
    """Школьный учебник и программа; без ЦТ/ЦЭ/РТ."""
    return qs.filter(SCHOOL_TEXTBOOK_INCLUDE_Q).exclude(SCHOOL_TEXTBOOK_EXCLUDE_Q)
