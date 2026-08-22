from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings

from knowledge.management.commands.import_primary_pictures import SOURCE, _mc
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
        payload = response.json()
        self.assertEqual(payload['items'], payload['subjects'])
        grades = payload['items'][0]['grades']
        self.assertEqual(grades[4]['task_count'], 2)
        self.assertEqual(grades[4]['tasks'], 2)
        self.assertEqual(grades[4]['topics'], 1)
        self.assertTrue(grades[4]['available'])
        self.assertEqual(grades[4]['title'], '5 класс')
        self.assertEqual(grades[5]['task_count'], 0)
        self.assertFalse(grades[5]['available'])

    def test_primary_import_repairs_missing_image_without_duplicate_task(self):
        subject = Subject.objects.create(name='Русский язык', slug='repair-ru')
        track = ExamTrack.objects.create(
            subject=subject,
            name='Школьная программа',
            track_type=ExamTrack.TrackType.GENERAL,
        )
        version = ContentVersion.objects.create(subject=subject, year=2027, title='2027')
        section = Section.objects.create(
            exam_track=track,
            content_version=version,
            name='Буквы',
        )
        topic = Topic.objects.create(section=section, name='Гласные', grade_level=1)
        task = Task.objects.create(
            topic=topic,
            source=SOURCE,
            question='Какая буква?',
            image='tasks/missing.png',
        )

        with TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            source_image = Path(tmp) / 'generated.png'
            source_image.write_bytes(b'generated-image')

            created = _mc(
                topic,
                task.question,
                ['А', 'О'],
                'Это А.',
                image_path=source_image,
            )
            task.refresh_from_db()

            self.assertFalse(created)
            self.assertEqual(Task.objects.filter(question=task.question).count(), 1)
            self.assertTrue(task.image.storage.exists(task.image.name))
