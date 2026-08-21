"""Сервисы доступа и проверки лимитов (async)."""

from core.models import AppSettings


async def aget_app_settings() -> AppSettings:
    return await AppSettings.aget_settings()


async def student_can_practice(student) -> tuple[bool, str]:
    """Проверяет, может ли ученик решать задания сейчас."""
    settings = await aget_app_settings()

    if student.has_active_pro:
        return True, ''

    if not settings.free_mode_enabled:
        return False, 'Бесплатный режим отключён. Оформите Pro-подписку.'

    if student.daily_tasks_completed >= settings.free_daily_tasks_limit:
        return (
            False,
            f'Достигнут лимит бесплатных заданий на сегодня ({settings.free_daily_tasks_limit}). '
            'Оформите Pro для безлимита.',
        )

    return True, ''


async def student_can_request_ai(student) -> tuple[bool, bool, str]:
    """
    ИИ-разбор ошибок.
    Возвращает (можно_просить, use_llm, причина).
    Free: только эталон/конспект из БД (без LLM), если включено в настройках.
    Pro: grounded LLM-пересказ по эталону (не генерация заданий).
    """
    settings = await aget_app_settings()

    if student.has_active_pro:
        if settings.pro_ai_explanations_enabled:
            return True, True, ''
        return False, False, 'ИИ-разбор временно недоступен для Pro.'

    if not settings.free_mode_enabled:
        return False, False, 'Разбор доступен в Pro-подписке.'

    if settings.free_ai_explanations_enabled:
        # free: локальный разбор без модели
        return True, False, ''

    return False, False, 'Подробный ИИ-разбор — в Pro. Эталон ответа всё равно показывается после ошибки.'