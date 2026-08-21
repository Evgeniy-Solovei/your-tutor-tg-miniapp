from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Ядро'

    def ready(self):
        try:
            from core.models import AppSettings

            AppSettings.objects.get_or_create(pk=1)
        except Exception:
            pass
