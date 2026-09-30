"""Задания, импортированные из школьных учебников (не ЦТ/не сид-квизы)."""

from __future__ import annotations

from django.db.models import Q

# Полный текст упражнения (2–11) или страница учебника (1 класс).
SCHOOL_TEXTBOOK_SOURCE_Q = Q(source__contains='полный текст') | Q(
    source__startswith='Учебник «Русский язык» 1 класс, стр.'
)


def filter_school_textbook_tasks(qs):
    return qs.filter(SCHOOL_TEXTBOOK_SOURCE_Q)
