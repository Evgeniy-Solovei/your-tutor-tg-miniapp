#!/bin/bash
set -e

echo "🗄 Проверка, генерация и выполнение миграций базы данных..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
python manage.py setup_project || true

echo "🚀 Запуск Web сервера (Gunicorn на порту 8005)..."
exec gunicorn --workers 3 --bind 0.0.0.0:8005 --access-logfile - --error-logfile - tutor_bot.wsgi:application
