"""Создаёт треки ЦТ / ЦЭ / аттестат 9 / общая подготовка."""

from django.core.management.base import BaseCommand

from knowledge.models import ExamTrack, Subject


TRACKS = [
    {
        'track_type': ExamTrack.TrackType.CT_11,
        'name': 'ЦТ по русскому языку (после 11 класса)',
        'grade_from': 10,
        'grade_to': 11,
    },
    {
        'track_type': ExamTrack.TrackType.CE_11,
        'name': 'ЦЭ по русскому языку (после 11 класса)',
        'grade_from': 10,
        'grade_to': 11,
    },
    {
        'track_type': ExamTrack.TrackType.ATTESTAT_9,
        'name': 'Аттестат / базовое образование (после 9 класса)',
        'grade_from': 8,
        'grade_to': 9,
    },
    {
        'track_type': ExamTrack.TrackType.GENERAL,
        'name': 'Школьная программа (1–11 классы)',
        'grade_from': 1,
        'grade_to': 11,
    },
]


class Command(BaseCommand):
    help = 'Создаёт ExamTrack для всех целей (ЦТ, ЦЭ, 9 класс, общая)'

    def handle(self, *args, **options):
        subject, _ = Subject.objects.get_or_create(
            slug='russian',
            defaults={
                'name': 'Русский язык',
                'description': 'Подготовка к ЦТ/ЦЭ и аттестату (Беларусь)',
                'order': 1,
                'is_active': True,
            },
        )
        # старый объединённый трек — переименуем, если есть
        old = ExamTrack.objects.filter(
            subject=subject, track_type=ExamTrack.TrackType.CT_11
        ).first()
        if old and 'ЦТ / ЦЭ' in old.name:
            old.name = TRACKS[0]['name']
            old.grade_from = TRACKS[0]['grade_from']
            old.grade_to = TRACKS[0]['grade_to']
            old.save(update_fields=['name', 'grade_from', 'grade_to'])

        for spec in TRACKS:
            track, created = ExamTrack.objects.update_or_create(
                subject=subject,
                track_type=spec['track_type'],
                defaults={
                    'name': spec['name'],
                    'grade_from': spec['grade_from'],
                    'grade_to': spec['grade_to'],
                    'is_active': True,
                },
            )
            self.stdout.write(
                f'{"+ " if created else "= "}{track.track_type}: {track.name}'
            )
        self.stdout.write(self.style.SUCCESS('Готово. В админке будут все 4 трека.'))
