"""Перенос заданий про правила ЖИ-ШИ / ЧА-ЩА из чужих тем в тему орфографии.

Только явные формулировки правил — не любое слово с «ча»/«жи» в тексте.
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db.models import Q

from knowledge.models import Task, Topic

# Только явные маркеры правил (не «чайка», не «жизнь» в обычном тексте).
ORTHO_Q = (
    Q(question__icontains='ЧА - ЩА')
    | Q(question__icontains='ЧА—ЩА')
    | Q(question__icontains='ча - ща')
    | Q(question__icontains='ча-ща')
    | Q(question__icontains='ЖИ - ШИ')
    | Q(question__icontains='ЖИ—ШИ')
    | Q(question__icontains='жи-ши')
    | Q(question__icontains='жи — ши')
    | Q(question__icontains='ЧУ - ЩУ')
    | Q(question__icontains='ЧУ—ЩУ')
    | Q(question__icontains='чу-щу')
    | Q(question__icontains='ЧК, ЧН')
    | Q(question__icontains='ЧК-ЧН')
    | Q(question__icontains='буквосочетани')
    | Q(question__icontains='пиши с буквой И')
    | Q(question__icontains='пиши с буквой А')
    | Q(question__icontains='пиши с буквой У')
    | Q(question__icontains='сочетания ЧА')
    | Q(question__icontains='сочетания ЖИ')
)

ORTHO_TOPIC_NAMES = {
    1: ['Буквосочетания ЧА - ЩА', 'Буквосочетания ЖИ - ШИ', 'Тренажёр ЧА - ЩА'],
    2: ['Правописание ЖИ-ШИ, ЧА-ЩА, ЧУ-ЩУ, ЧК-ЧН'],
}

KEEP_NAME_RE = re.compile(
    r'(жи.?ши|ча.?ща|чу.?щу|чк.?чн|буквосочетан|правописание жи|тренажёр ча)',
    re.I,
)


class Command(BaseCommand):
    help = 'Уводит явные задания ЖИ/ЧА/ЩА из чужих тем в тему орфографии'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--grade', type=int, default=0)

    def _pick_target(self, grade: int, question: str) -> Topic | None:
        names = ORTHO_TOPIC_NAMES.get(grade) or []
        q = (question or '').upper()
        preferred = names
        if grade == 1:
            if 'ЖИ' in q or 'ШИ' in q:
                preferred = ['Буквосочетания ЖИ - ШИ'] + names
            elif 'ЧА' in q or 'ЩА' in q:
                preferred = ['Буквосочетания ЧА - ЩА', 'Тренажёр ЧА - ЩА'] + names
        for name in preferred:
            t = Topic.objects.filter(grade_level=grade, is_active=True, name=name).first()
            if t:
                return t
        return (
            Topic.objects.filter(grade_level=grade, is_active=True)
            .filter(Q(name__icontains='ЧА') | Q(name__icontains='ЖИ-ШИ'))
            .first()
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        grades = [options['grade']] if options['grade'] else [1, 2]
        moved = 0
        for grade in grades:
            qs = (
                Task.objects.filter(is_active=True, topic__grade_level=grade)
                .filter(ORTHO_Q)
                .exclude(topic__name__iregex=KEEP_NAME_RE.pattern)
                .select_related('topic')
            )
            n = qs.count()
            self.stdout.write(f'{grade} кл.: кандидатов {n}')
            if dry:
                for task in qs[:5]:
                    self.stdout.write(f'  #{task.id} «{task.topic.name}» ← {(task.question or "")[:70]}')
                continue
            by_target: dict[int, list[int]] = {}
            for task in qs.iterator():
                target = self._pick_target(grade, task.question or '')
                if not target or target.id == task.topic_id:
                    continue
                by_target.setdefault(target.id, []).append(task.id)
            for tid, ids in by_target.items():
                updated = Task.objects.filter(id__in=ids).update(topic_id=tid)
                moved += updated
                tname = Topic.objects.filter(id=tid).values_list('name', flat=True).first()
                self.stdout.write(self.style.SUCCESS(f'  → «{tname}»: {updated}'))
        self.stdout.write(self.style.SUCCESS(f'Итого перенесено: {moved}'))
