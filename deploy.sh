#!/bin/bash
# ==============================================================================
# 🚀 Автоматический Скрипт Полного Развертывания Tutor Bot на VPS
# ==============================================================================

set -e

echo "📦 1/6 Обновление системных пакетов и установка зависимостей..."
sudo apt update
sudo apt install -y python3-pip python3-venv postgresql redis-server nginx certbot python3-certbot-nginx

echo "🐍 2/6 Создание Python venv и установка библиотек..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

echo "🗄 3/6 Выполнение миграций базы данных и сборка статики..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "👤 4/6 Проверка администратора..."
python manage.py create_admin || true

echo "🌐 5/6 Настройка Nginx..."
if [ -f "nginx.conf.example" ]; then
    sudo cp nginx.conf.example /etc/nginx/sites-available/tutorbot
    sudo ln -sf /etc/nginx/sites-available/tutorbot /etc/nginx/sites-enabled/tutorbot
    sudo systemctl restart nginx
fi

echo "⚙️ 6/6 Регистрация и Автозапуск системных служб (Systemd Services)..."
if [ -f "tutor-web.service" ] && [ -f "tutor-bot.service" ]; then
    sudo cp tutor-web.service /etc/systemd/system/
    sudo cp tutor-bot.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable tutor-web tutor-bot
    sudo systemctl restart tutor-web tutor-bot
fi

echo "======================================================================"
echo "🎉 ВСЁ ГОТОВО И ЗАПУЩЕНО В ФОНЕ (Systemd Автозапуск)!"
echo "- Сайт/API: systemctl status tutor-web"
echo "- Бот:      systemctl status tutor-bot"
echo "----------------------------------------------------------------------"
echo "Осталось только получить SSL (HTTPS) сертификат:"
echo "   sudo certbot --nginx -d your-tutor.live-dev.by"
echo "======================================================================"
