from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings


class MediaFileTests(TestCase):
    def test_media_file_is_served_in_production_route(self):
        with TemporaryDirectory() as tmp, override_settings(
            MEDIA_ROOT=tmp,
            SECURE_SSL_REDIRECT=False,
        ):
            image = Path(tmp) / 'tasks' / 'picture.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'fake-png-content')

            response = self.client.get('/media/tasks/picture.png')

            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'fake-png-content')
            self.assertEqual(response['Content-Type'], 'image/png')

    def test_missing_media_file_returns_404(self):
        with TemporaryDirectory() as tmp, override_settings(
            MEDIA_ROOT=tmp,
            SECURE_SSL_REDIRECT=False,
        ):
            response = self.client.get('/media/tasks/missing.png')

        self.assertEqual(response.status_code, 404)
