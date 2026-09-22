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


from knowledge.models import TopicExtraTask
from students.models import Student
from learning.models import TaskAttempt, TopicMastery


@override_settings(DEBUG=True, TELEGRAM_AUTH_BYPASS=True)
class ExtraTasksTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Русский язык', slug='extra-ru')
        self.track = ExamTrack.objects.create(
            subject=self.subject,
            name='Школьная программа',
            track_type=ExamTrack.TrackType.GENERAL,
        )
        self.version = ContentVersion.objects.create(subject=self.subject, year=2026, title='2026')
        self.section = Section.objects.create(
            exam_track=self.track,
            content_version=self.version,
            name='Орфография',
        )
        self.topic = Topic.objects.create(section=self.section, name='Буквосочетания ЖИ-ШИ', grade_level=1)
        self.student = Student.objects.create(
            tg_id=88801,
            display_name='Test Learner',
            grade=1,
            goal=Student.Goal.IMPROVE,
            subject=self.subject,
            exam_track=self.track,
            registration_completed=True,
            xp=0,
        )
        self.extra_task = TopicExtraTask.objects.create(
            topic=self.topic,
            question='Вставь букву в слове «м...ши»',
            options=['И', 'Ы', 'Е'],
            correct_answer='И',
            explanation='ЖИ пиши с И',
            difficulty=TopicExtraTask.Difficulty.EASY,
            order=1,
        )

    def test_extra_tasks_summary_endpoint(self):
        res = self.client.get(f'/api/tutor/knowledge/extra-tasks/summary/?grade=1&tg_id={self.student.tg_id}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['grade'], 1)
        self.assertEqual(data['total_extra_tasks'], 1)
        self.assertEqual(len(data['topics']), 1)
        self.assertEqual(data['topics'][0]['topic_id'], self.topic.id)
        self.assertEqual(data['topics'][0]['extra_tasks_count'], 1)
        self.assertEqual(data['topics'][0]['solved_count'], 0)

    def test_topic_extra_tasks_list_endpoint(self):
        res = self.client.get(f'/api/tutor/knowledge/topics/{self.topic.id}/extra-tasks/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['topic_id'], self.topic.id)
        self.assertEqual(len(data['tasks']), 1)
        self.assertEqual(data['tasks'][0]['question'], 'Вставь букву в слове «м...ши»')
        self.assertEqual(data['tasks'][0]['options'], ['И', 'Ы', 'Е'])
        self.assertNotIn('correct_answer', data['tasks'][0])

    def test_submit_extra_task_answer_correct(self):
        res = self.client.post(
            f'/api/tutor/knowledge/extra-tasks/{self.extra_task.id}/answer/',
            data={'answer': 'И', 'tg_id': self.student.tg_id},
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['is_correct'])
        self.assertEqual(data['xp_earned'], 10)
        self.student.refresh_from_db()
        self.assertEqual(self.student.xp, 10)

        attempt = TaskAttempt.objects.filter(student=self.student, extra_task=self.extra_task).first()
        self.assertIsNotNone(attempt)
        self.assertTrue(attempt.is_correct)

    def test_payment_return_page_served(self):
        res = self.client.get('/app/payment-return.html?status=success&bot=tutor_by_bot')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/html', res['Content-Type'])
        content = b''.join(res.streaming_content).decode('utf-8')
        self.assertIn('Оплата успешно проведена', content)

