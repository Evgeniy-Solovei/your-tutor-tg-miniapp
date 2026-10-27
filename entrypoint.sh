#!/bin/bash
set -e

echo "🗄 Выполнение версионированных миграций базы данных..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

# Прогрев кэша программ классов (без COUNT по 760k доп. — быстрый Exists)
echo "🔥 Прогрев curriculum cache..."
python manage.py shell -c "
from asgiref.sync import async_to_sync
from knowledge.views import _curriculum_base_payload
for g in range(1, 12):
    try:
        async_to_sync(_curriculum_base_payload)(g)
        print('  grade', g, 'ok')
    except Exception as e:
        print('  grade', g, e)
" || true

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
