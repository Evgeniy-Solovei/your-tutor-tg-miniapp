import json
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone
from students.models import Student
from knowledge.models import Subject, Topic, Task, TaskOption, ExamVariant, VariantTask, ExamTrack, Section, ContentVersion, ExamCollection, TaskSolution
from learning.models import DailySession, SessionTask
from learning.services import create_exam_simulator_session, submit_exam_simulator


@override_settings(DEBUG=True, TELEGRAM_AUTH_BYPASS=True, SECURE_SSL_REDIRECT=False)
class SubmitChoiceAnswerApiTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Русский язык', slug='choice-answer-ru')
        track = ExamTrack.objects.create(
            subject=subject,
            name='Школьная программа',
            track_type=ExamTrack.TrackType.GENERAL,
        )
        version = ContentVersion.objects.create(subject=subject, year=2026, title='2026')
        section = Section.objects.create(
            exam_track=track,
            content_version=version,
            name='Слоги',
        )
        topic = Topic.objects.create(section=section, name='Слоги', grade_level=1)
        self.student = Student.objects.create(
            tg_id=445566,
            display_name='Ученик',
            grade=1,
            subject=subject,
            exam_track=track,
            goal=Student.Goal.IMPROVE,
            registration_completed=True,
        )
        self.task = Task.objects.create(
            topic=topic,
            question='Сколько слогов в слове «мама»?',
            answer_format=Task.AnswerFormat.SINGLE_CHOICE,
            scoring_scheme=Task.ScoringScheme.BINARY_1,
        )
        self.correct_option = TaskOption.objects.create(
            task=self.task,
            text='2',
            is_correct=True,
            order=1,
        )
        self.wrong_option = TaskOption.objects.create(
            task=self.task,
            text='1',
            is_correct=False,
            order=2,
        )
        TaskSolution.objects.create(
            task=self.task,
            correct_answer='1',
            explanation='ма-ма — два слога.',
        )

    def make_session_task(self):
        session = DailySession.objects.create(
            student=self.student,
            session_date=timezone.localdate(),
            kind=DailySession.Kind.TRAIN,
            status=DailySession.Status.IN_PROGRESS,
            tasks_total=1,
        )
        return SessionTask.objects.create(session=session, task=self.task, order=1)

    def submit(self, session_task, option, misleading_answer):
        return self.client.post(
            f'/api/tutor/submit-answer/{self.student.tg_id}/',
            data=json.dumps({
                'session_task_id': session_task.id,
                'answer_text': misleading_answer,
                'selected_option_ids': [option.id],
            }),
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )

    def test_selected_option_id_is_used_for_grading(self):
        response = self.submit(self.make_session_task(), self.correct_option, '2')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_correct'])

    def test_wrong_answer_returns_human_readable_correct_option(self):
        response = self.submit(self.make_session_task(), self.wrong_option, '1')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['is_correct'])
        self.assertEqual(response.json()['correct_answer'], '2')

    def test_options_contain_id_text_and_order(self):
        st = self.make_session_task()
        st.task._prefetched_objects_cache = {'options': [self.correct_option, self.wrong_option]}
        from learning.views import serialize_current_task
        import asyncio
        serialized = asyncio.run(serialize_current_task(st))
        self.assertEqual(len(serialized['options']), 2)
        opt_ids = {opt['id'] for opt in serialized['options']}
        self.assertEqual(opt_ids, {self.correct_option.id, self.wrong_option.id})
        for opt in serialized['options']:
            self.assertIn('order', opt)
            self.assertIn('text', opt)


class ExamSimulatorTestCase(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Русский язык", slug="ru")
        self.track = ExamTrack.objects.create(
            subject=self.subject,
            name="Подготовка к ЦТ",
            track_type=ExamTrack.TrackType.CT_11,
        )
        self.student = Student.objects.create(
            tg_id=123456789,
            display_name="Тестовый Ученик",
            grade=11,
            subject=self.subject,
            exam_track=self.track,
            goal=Student.Goal.CT,
        )
        self.version = ContentVersion.objects.create(
            subject=self.subject,
            year=2025,
            title="Версия 2025",
            is_current=True,
        )
        self.section = Section.objects.create(
            exam_track=self.track,
            content_version=self.version,
            name="Основной раздел",
            order=1,
        )
        self.topic = Topic.objects.create(
            section=self.section,
            name="Орфография",
            order=1,
        )

        # Создадим 40 тестовых заданий (30 Часть А, 10 Часть Б)
        self.collection = ExamCollection.objects.create(
            subject=self.subject,
            title="Сборник ЦТ 2025",
            year=2025,
        )
        self.variant = ExamVariant.objects.create(
            collection=self.collection,
            number=1,
            title="Вариант 1",
            year=2025,
        )
        for i in range(1, 41):
            is_part_b = i > 30
            task = Task.objects.create(
                topic=self.topic,
                question=f"Вопрос {i}",
                answer_format=Task.AnswerFormat.MULTIPLE_CHOICE if not is_part_b else Task.AnswerFormat.TEXT,
            )
            TaskSolution.objects.create(
                task=task,
                correct_answer="1,3" if not is_part_b else "ОТВЕТ",
                explanation="Объяснение",
            )
            VariantTask.objects.create(
                variant=self.variant,
                task=task,
                order=i,
            )

    async def test_create_and_submit_exam_simulator(self):
        session = await create_exam_simulator_session(self.student, variant_id=self.variant.id)
        self.assertEqual(session.kind, DailySession.Kind.EXAM)
        self.assertEqual(session.tasks_total, 40)
        self.assertEqual(session.time_limit_seconds, 10800)

        tasks_count = await SessionTask.objects.filter(session=session).acount()
        self.assertEqual(tasks_count, 40)

        # Подготовим ответы
        session_tasks = [
            st async for st in SessionTask.objects.filter(session=session).order_by('order')
        ]
        answers = []
        for st in session_tasks:
            answers.append({
                'session_task_id': st.id,
                'answer_text': '1,3' if st.order <= 30 else 'ОТВЕТ',
            })

        protocol = await submit_exam_simulator(
            self.student, session, answers, time_spent_seconds=3600
        )
        self.assertIn('test_score', protocol)
        self.assertIn('primary_score', protocol)
        self.assertEqual(protocol['tasks_total'], 40)
        self.assertGreater(protocol['test_score'], 0)

    async def test_exam_without_variant_uses_text_tasks_for_part_b(self):
        session = await create_exam_simulator_session(self.student)
        self.assertEqual(session.tasks_total, 40)
        formats = [
            value
            async for value in SessionTask.objects.filter(session=session)
            .values_list('task__answer_format', flat=True)
        ]
        self.assertEqual(formats.count(Task.AnswerFormat.TEXT), 10)


from learning.models import WeeklyLeague
from students.models import PaymentOrder


class NewFeaturesTestCase(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Математика", slug="math")
        self.track = ExamTrack.objects.create(
            subject=self.subject,
            name="Подготовка к ЦТ",
            track_type=ExamTrack.TrackType.CT_11,
        )
        self.student = Student.objects.create(
            tg_id=999888777,
            display_name="Тестовый Игрок",
            grade=11,
            subject=self.subject,
            exam_track=self.track,
            goal=Student.Goal.CT,
            registration_completed=True,
        )

    def test_weekly_league_prizes(self):
        today = datetime.date.today()
        league = WeeklyLeague.objects.create(
            title="Осенний Супер-турнир",
            period_type=WeeklyLeague.PeriodType.WEEK,
            week_start=today,
            week_end=today + datetime.timedelta(days=7),
            prize_first_place="🥇 1 место: Подписка Яндекс Плюс",
            prize_second_place="🥈 2 место: Telegram Premium",
            prize_third_place="🥉 3 место: Pro-доступ",
            prizes_text="Спонсор турнира: Школа 2026",
            is_active=True,
        )
        self.assertEqual(league.title, "Осенний Супер-турнир")
        self.assertEqual(league.period_type, "week")
        self.assertTrue(league.is_active)

    def test_payment_order_bepaid(self):
        order = PaymentOrder.objects.create(
            order_id="PAY-TEST123456",
            student=self.student,
            plan_code="pro_1m",
            amount_byn=19.90,
            days=30,
            status=PaymentOrder.Status.PENDING,
            bepaid_checkout_url="https://checkout.bepaid.by/v2/checkout?token=test_PAY-TEST123456",
        )
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.amount_byn, 19.90)

        # Симулируем оплату
        order.status = PaymentOrder.Status.PAID
        order.paid_at = timezone.now()
        order.save()

        self.student.is_pro = True
        self.student.pro_until = timezone.now() + datetime.timedelta(days=30)
        self.student.save()

        self.assertTrue(self.student.has_active_pro)


@override_settings(DEBUG=True, TELEGRAM_AUTH_BYPASS=True, SECURE_SSL_REDIRECT=False)
class TrainSessionModesTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Русский язык', slug='modes-ru')
        self.track = ExamTrack.objects.create(
            subject=self.subject,
            name='ЦТ и ЦЭ',
            track_type=ExamTrack.TrackType.CT_11,
        )
        self.track_school = ExamTrack.objects.create(
            subject=self.subject,
            name='Школа',
            track_type=ExamTrack.TrackType.GENERAL,
        )
        version = ContentVersion.objects.create(subject=self.subject, year=2026, title='2026')
        section11 = Section.objects.create(exam_track=self.track, content_version=version, name='Тесты 11')
        section9 = Section.objects.create(exam_track=self.track_school, content_version=version, name='Тесты 9')
        self.topic11 = Topic.objects.create(section=section11, name='Орфография', grade_level=11)
        self.topic9 = Topic.objects.create(section=section9, name='Синтаксис 9', grade_level=9)

        # 11 grade Part A (choice)
        self.task_a = Task.objects.create(
            topic=self.topic11,
            question='Вопрос части А',
            answer_format=Task.AnswerFormat.SINGLE_CHOICE,
            source='РИКЗ',
        )
        TaskOption.objects.create(task=self.task_a, text='Вариант 1', is_correct=True, order=1)
        TaskSolution.objects.create(task=self.task_a, correct_answer='1')

        # 11 grade Part B (open text)
        self.task_b = Task.objects.create(
            topic=self.topic11,
            question='Вопрос части Б [В1]',
            answer_format=Task.AnswerFormat.TEXT,
            source='РИКЗ',
        )
        TaskSolution.objects.create(task=self.task_b, correct_answer='приставка')

        # 9 grade school task
        self.task_9_school = Task.objects.create(
            topic=self.topic9,
            question='Школьное задание 9 класс',
            answer_format=Task.AnswerFormat.SINGLE_CHOICE,
            source='Учебник 9 класс',
        )
        TaskOption.objects.create(task=self.task_9_school, text='Ответ', is_correct=True, order=1)
        TaskSolution.objects.create(task=self.task_9_school, correct_answer='1')

        # 9 grade izlozhenie
        self.task_9_izlo = Task.objects.create(
            topic=self.topic9,
            question='Текст изложения',
            answer_format=Task.AnswerFormat.TEXT,
            source='Сборник изложений для экзамена',
        )
        TaskSolution.objects.create(task=self.task_9_izlo, correct_answer='Текст')

        self.student = Student.objects.create(
            tg_id=778899,
            display_name='Абитуриент',
            grade=11,
            subject=self.subject,
            exam_track=self.track,
            registration_completed=True,
        )

    def test_post_daily_session_part_a(self):
        res = self.client.post(
            f'/api/tutor/daily-session/{self.student.tg_id}/',
            data=json.dumps({'mode': 'part_a', 'grade': 11}),
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['can_practice'])
        self.assertTrue(data['content_available'])
        self.assertEqual(data['current_task']['answer_format'], 'single_choice')

    def test_post_daily_session_part_b(self):
        res = self.client.post(
            f'/api/tutor/daily-session/{self.student.tg_id}/',
            data=json.dumps({'mode': 'part_b', 'grade': 11}),
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['can_practice'])
        self.assertTrue(data['content_available'])
        self.assertEqual(data['current_task']['answer_format'], 'text')
        self.assertIn('[В1]', data['current_task']['question'])

    def test_grade_curriculum_extra_stats(self):
        # 11 grade stats
        res11 = self.client.get(
            '/api/tutor/knowledge/grade/11/',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res11.status_code, 200)
        d11 = res11.json()
        self.assertTrue(d11.get('has_ct_ce'))
        self.assertEqual(d11.get('part_a_count'), 1)
        self.assertEqual(d11.get('part_b_count'), 1)

        # 9 grade stats
        res9 = self.client.get(
            '/api/tutor/knowledge/grade/9/',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res9.status_code, 200)
        d9 = res9.json()
        self.assertTrue(d9.get('has_izlozheniya'))
        self.assertEqual(d9.get('izlozheniya_count'), 1)
        self.assertEqual(d9.get('school_tasks_count'), 1)
        self.assertTrue(len(d9.get('collections', [])) > 0)

    def test_grade_1_has_no_extra_materials(self):
        res = self.client.get(
            '/api/tutor/knowledge/grade/1/',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data.get('has_extra_materials'))
        self.assertEqual(len(data.get('collections', [])), 0)

    def test_grade_11_available_years(self):
        res = self.client.get(
            '/api/tutor/knowledge/grade/11/',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('available_years', data)
        self.assertTrue(len(data['available_years']) > 0)
        self.assertTrue(len(data.get('collections', [])) > 0)
        self.assertTrue(data.get('has_extra_materials'))

    def test_post_daily_session_with_year(self):
        # We set task_a source to 'ЦТ 2024 Вариант 1'
        self.task_a.source = 'ЦТ 2024 Вариант 1'
        self.task_a.save()

        res = self.client.post(
            f'/api/tutor/daily-session/{self.student.tg_id}/',
            data=json.dumps({'mode': 'part_a', 'grade': 11, 'year': 2024}),
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['can_practice'])
        self.assertTrue(data['content_available'])
        self.assertIn('2024', data['current_task']['source'])

    def test_exam_start_with_year(self):
        self.task_a.source = 'ЦТ 2024'
        self.task_a.save()

        res = self.client.post(
            f'/api/tutor/exam/{self.student.tg_id}/start/',
            data=json.dumps({'year': 2024}),
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('session_id', data)
        self.assertTrue(len(data['tasks']) > 0)
