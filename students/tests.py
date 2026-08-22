import base64
import json
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from django.test import TestCase, override_settings
from django.test import RequestFactory
from django.utils import timezone

from knowledge.models import ExamTrack, Subject
from students.models import PaymentOrder, Student
from students.views_analytics import admin_analytics_view


@override_settings(
    BEPAID_SHOP_ID='4225',
    BEPAID_SECRET_KEY='test-secret',
    BEPAID_TEST_MODE=True,
)
class BePaidWebhookTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Русский язык', slug='webhook-ru')
        track = ExamTrack.objects.create(
            subject=subject,
            name='ЦТ',
            track_type=ExamTrack.TrackType.CT_11,
        )
        self.student = Student.objects.create(
            tg_id=70001,
            display_name='Webhook Student',
            grade=11,
            goal=Student.Goal.CT,
            subject=subject,
            exam_track=track,
            registration_completed=True,
        )
        self.order = PaymentOrder.objects.create(
            order_id='PAY-WEBHOOK-1',
            student=self.student,
            amount_byn='19.90',
            days=30,
        )
        token = base64.b64encode(b'4225:test-secret').decode()
        self.headers = {'HTTP_AUTHORIZATION': f'Basic {token}'}
        self.payload = {
            'transaction': {
                'tracking_id': self.order.order_id,
                'status': 'successful',
                'amount': 1990,
                'currency': 'BYN',
                'test': True,
            }
        }

    def post_webhook(self, payload=None, **headers):
        return self.client.post(
            '/api/tutor/payments/bepaid/webhook/',
            data=json.dumps(payload or self.payload),
            content_type='application/json',
            **headers,
        )

    def test_rejects_unsigned_webhook(self):
        response = self.post_webhook()
        self.assertEqual(response.status_code, 401)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PaymentOrder.Status.PENDING)

    def test_rejects_wrong_amount(self):
        payload = {'transaction': {**self.payload['transaction'], 'amount': 1}}
        response = self.post_webhook(payload, **self.headers)
        self.assertEqual(response.status_code, 400)

    @override_settings(DEBUG=True, TELEGRAM_AUTH_BYPASS=True)
    @patch('httpx.AsyncClient.post', new_callable=AsyncMock)
    def test_checkout_uses_bepaid_token_endpoint_and_settings(self, post):
        post.return_value = Mock(status_code=201)
        post.return_value.json.return_value = {
            'checkout': {
                'token': 'test-token',
                'redirect_url': 'https://checkout.bepaid.by/v2/checkout?token=test-token',
            }
        }
        response = self.client.post(
            '/api/tutor/payments/bepaid/checkout/',
            data=json.dumps({'plan_code': 'pro_1m'}),
            content_type='application/json',
            HTTP_TELEGRAM_DEV_USER=str(self.student.tg_id),
        )
        self.assertEqual(response.status_code, 200)
        url = post.await_args.args[0]
        checkout = post.await_args.kwargs['json']['checkout']
        self.assertEqual(url, 'https://checkout.bepaid.by/ctp/api/checkouts')
        self.assertIn('notification_url', checkout['settings'])
        self.assertNotIn('notification_url', {key: value for key, value in checkout.items() if key != 'settings'})
        self.assertTrue(checkout['test'])

    @patch('students.views.send_telegram_message', new_callable=AsyncMock)
    def test_successful_webhook_is_idempotent(self, send_message):
        first = self.post_webhook(**self.headers)
        self.assertEqual(first.status_code, 200)
        self.student.refresh_from_db()
        first_pro_until = self.student.pro_until
        self.assertGreater(first_pro_until, timezone.now() + timedelta(days=29))

        second = self.post_webhook(**self.headers)
        self.assertEqual(second.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.pro_until, first_pro_until)
        self.assertEqual(send_message.await_count, 1)


class SettingsPermissionTests(TestCase):
    def test_web_app_url_cannot_be_changed_anonymously(self):
        response = self.client.post(
            '/api/tutor/config/web-app-url/',
            data=json.dumps({'url': 'https://attacker.example'}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, (401, 403))


class AdminAnalyticsQueryTests(TestCase):
    def test_dashboard_uses_three_aggregate_queries(self):
        request = RequestFactory().get('/admin/analytics/')
        with self.assertNumQueries(3):
            response = admin_analytics_view(request)
        self.assertEqual(response.status_code, 200)
