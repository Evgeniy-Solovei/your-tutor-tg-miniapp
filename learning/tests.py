from django.test import TestCase
from students.models import Student
from knowledge.models import Subject, Topic, Task, ExamVariant, VariantTask, ExamTrack, Section, ContentVersion, ExamCollection, TaskSolution
from learning.models import DailySession, SessionTask
from learning.services import create_exam_simulator_session, submit_exam_simulator


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


from learning.models import WeeklyLeague
from students.models import PaymentOrder
from django.utils import timezone
import datetime


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


