import asyncio
from celery import shared_task
from django.core.management import call_command


@shared_task
def send_daily_reminders_task():
    """Фоновая задача Celery: отправка 5 заданий дня ученикам."""
    call_command('send_daily_reminders')
    return 'Daily reminders sent successfully'


@shared_task
def send_weekly_parent_reports_task():
    """Фоновая задача Celery: отправка отчётов родителям за неделю."""
    call_command('send_weekly_parent_reports')
    return 'Weekly parent reports sent successfully'
