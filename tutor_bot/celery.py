import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutor_bot.settings')

app = Celery('tutor_bot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Дневные рассылки ученикам каждый день в 10:00 (МСК / Минск)
    'send-daily-reminders-everyday': {
        'task': 'learning.tasks.send_daily_reminders_task',
        'schedule': crontab(hour=10, minute=0),
    },
    # Еженедельные отчёты родителям каждое воскресенье в 18:00
    'send-weekly-parent-reports-sunday': {
        'task': 'learning.tasks.send_weekly_parent_reports_task',
        'schedule': crontab(day_of_week=0, hour=18, minute=0),
    },
}
