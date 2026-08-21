"""Загрузка шкалы первичный→тестовый балл РИКЗ."""

from django.core.management.base import BaseCommand

from knowledge.models import ExamTrack, ScoreScale, ScoreScaleRow, Task
from knowledge.score_tables import RU_BE_2025_SCALE
from learning.scoring import default_scoring_scheme


class Command(BaseCommand):
    help = 'Загружает шкалу баллов РИКЗ 2025 (русский) и проставляет схемы баллов заданиям'

    def handle(self, *args, **options):
        track = ExamTrack.objects.filter(is_active=True).order_by('id').first()
        if not track:
            self.stderr.write('Нет ExamTrack — сначала import_rikz_bank')
            return

        scale, created = ScoreScale.objects.update_or_create(
            exam_track=track,
            year=2025,
            defaults={
                'title': 'ЦЭ/ЦТ 2025 — Русский / Белорусский язык',
                'max_primary': 80,
                'source_url': 'https://rikc.by/ru/2025/01-02.pdf',
                'is_current': True,
            },
        )
        ScoreScale.objects.filter(exam_track=track).exclude(pk=scale.pk).update(is_current=False)

        rows = 0
        for primary, test in RU_BE_2025_SCALE.items():
            _, was = ScoreScaleRow.objects.update_or_create(
                scale=scale,
                primary_score=primary,
                defaults={'test_score': test},
            )
            rows += 1

        # схемы для существующих заданий открытого банка
        updated = 0
        for task in Task.objects.all().only('id', 'answer_format', 'scoring_scheme'):
            scheme = default_scoring_scheme(task.answer_format)
            if task.scoring_scheme != scheme:
                task.scoring_scheme = scheme
                task.save(update_fields=['scoring_scheme'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Шкала {"создана" if created else "обновлена"}: {scale}, строк={rows}, '
            f'схем заданий обновлено={updated}'
        ))
