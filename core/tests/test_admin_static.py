from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.templatetags.static import static


class AdminStaticTests(TestCase):
    def test_unfold_styles_are_discoverable(self):
        self.assertIsNotNone(finders.find('unfold/css/styles.css'))

    def test_admin_login_references_static_assets(self):
        get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='strong-test-password',
        )
        self.client.login(username='admin', password='strong-test-password')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, static('unfold/css/styles.css'))
