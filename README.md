# 🎓 Ваш Домашний Репетитор (Telegram Mini App)

Платформа подготовки к школьным урокам, ЦТ, ЦЭ и экзаменам РИКЗ с интерактивными тренажерами, турнирными лигами и ИИ-помощником.

## 🛠 Технологический стек
- **Backend**: Python 3.11+, Django 4.2 LTS, Django REST Framework, ADRF, Celery, Redis, PostgreSQL
- **Frontend**: Telegram Mini App (Vanilla JS + Custom UI Component Engine)
- **Оплата**: bePaid (ЕРИП, Visa, MasterCard, BELKART)
- **Интеграция ИИ**: GigaChat / DeepSeek API

## 🚀 Быстрый старт
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python telegram.py
```

## Проверки

Полный набор интеграционных тестов использует PostgreSQL из `.env`:

```bash
python manage.py test
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
```

Для быстрого локального smoke-прогона без запущенного PostgreSQL можно явно задать
`TEST_USE_SQLITE=True`; production и тесты по умолчанию от этого не меняются.

## Статика админки

`collectstatic` складывает Unfold/Django assets в `STATIC_ROOT`, а nginx проксирует
`/static/` в WhiteNoise на `127.0.0.1:8005`. Так конфигурация не зависит от доступа
пользователя `www-data` к `/root`.
