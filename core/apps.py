from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Ядро'

    def ready(self):
        # Регистрация расширений схемы не должна выполнять SQL при старте процесса.
        from core import schema  # noqa: F401
