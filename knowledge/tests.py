from django.test import TestCase

from knowledge.models import ContentVersion, ExamTrack, Section, Subject, Task, Topic


class CatalogApiTests(TestCase):
    def test_catalog_returns_grouped_task_counts(self):
        subject = Subject.objects.create(name='Русский язык', slug='catalog-ru')
        track = ExamTrack.objects.create(
            subject=subject,
            name='Школьная программа',
            track_type=ExamTrack.TrackType.GENERAL,
        )
        version = ContentVersion.objects.create(subject=subject, year=2026, title='2026')
        section = Section.objects.create(
            exam_track=track,
            content_version=version,
            name='Орфография',
        )
        topic = Topic.objects.create(section=section, name='Гласные', grade_level=5)
        Task.objects.bulk_create([
            Task(topic=topic, question='Задание 1'),
            Task(topic=topic, question='Задание 2'),
            Task(topic=topic, question='Неактивное', is_active=False),
        ])

        response = self.client.get('/api/tutor/knowledge/catalog/')
        self.assertEqual(response.status_code, 200)
        grades = response.json()['subjects'][0]['grades']
        self.assertEqual(grades[4]['task_count'], 2)
        self.assertEqual(grades[5]['task_count'], 0)
