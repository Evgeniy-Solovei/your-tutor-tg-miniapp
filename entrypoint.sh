#!/bin/bash
set -e

echo "🗄 Выполнение версионированных миграций базы данных..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

echo "🚀 Запуск Web сервера (Gunicorn на порту 8005)..."
exec gunicorn \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --bind 0.0.0.0:8005 \
    --access-logfile - \
    --error-logfile - \
    tutor_bot.wsgi:application
