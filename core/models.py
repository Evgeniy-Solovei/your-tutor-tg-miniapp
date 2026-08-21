from django.core.exceptions import ValidationError
from django.db import models


class AppSettings(models.Model):
    """Глобальные настройки приложения (singleton)."""

    free_mode_enabled = models.BooleanField(
        default=True,
        verbose_name='Бесплатный режим включён',
        help_text='Если выключено — доступ только у Pro-пользователей.',
    )
    free_daily_tasks_limit = models.PositiveSmallIntegerField(
        default=15,
        verbose_name='Лимит заданий в день (бесплатно)',
        help_text='Pro — без лимита. Для теста продукта можно поднять.',
    )
    free_ai_explanations_enabled = models.BooleanField(
        default=True,
        verbose_name='Базовый разбор в free (без LLM)',
        help_text='Показывает эталон+конспект. Живой LLM-разбор — только Pro.',
    )
    pro_ai_explanations_enabled = models.BooleanField(
        default=True,
        verbose_name='ИИ-разбор ошибок в Pro-режиме',
    )
    daily_session_tasks_count = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='Заданий в ежедневной сессии',
    )
    weak_topic_task_ratio = models.FloatField(
        default=0.6,
        verbose_name='Доля заданий по слабым темам (0–1)',
    )
    xp_per_correct_answer = models.PositiveSmallIntegerField(
        default=10,
        verbose_name='XP за правильный ответ',
    )
    streak_bonus_xp = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='Бонус XP за серию дней',
    )
    max_daily_xp = models.PositiveIntegerField(
        default=1000,
        verbose_name='Максимум XP в день (лимит турнира)',
        help_text='Максимальное количество XP, которое можно получить за 1 день для лидерборда.',
    )
    welcome_message = models.TextField(
        blank=True,
        verbose_name='Приветственное сообщение бота',
    )
    web_app_url = models.URLField(
        blank=True,
        verbose_name='URL мини-приложения (домен)',
        help_text='Например https://xxxx.ngrok-free.app или https://xxx.trycloudflare.com — без /app/. '
        'Приоритетнее WEB_APP_URL из .env. После смены перезапусти telegram.py.',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Настройки приложения'
        verbose_name_plural = 'Настройки приложения'

    def __str__(self):
        return 'Настройки приложения'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Нельзя удалить настройки приложения.')

    @classmethod
    async def aget_settings(cls):
        settings_obj, _ = await cls.objects.aget_or_create(pk=1)
        return settings_obj

    @classmethod
    def get_settings(cls):
        settings_obj, _ = cls.objects.get_or_create(pk=1)
        return settings_obj


class City(models.Model):
    """Город для рейтингов."""

    name = models.CharField(max_length=100, unique=True, verbose_name='Название города')
    region = models.CharField(max_length=100, blank=True, verbose_name='Область')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        ordering = ['name']

    def __str__(self):
        return self.name


class School(models.Model):
    """Школа для рейтингов."""

    name = models.CharField(max_length=255, verbose_name='Название школы')
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='schools',
        verbose_name='Город',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Школа'
        verbose_name_plural = 'Школы'
        ordering = ['city__name', 'name']
        unique_together = [('city', 'name')]

    def __str__(self):
        return f'{self.name} ({self.city.name})'
