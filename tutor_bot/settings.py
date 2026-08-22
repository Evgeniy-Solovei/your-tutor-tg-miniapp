import os
from pathlib import Path

from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-tutor-bot-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'your-tutor.live-dev.by,localhost,127.0.0.1').split(',')
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'https://your-tutor.live-dev.by,http://localhost:8000,http://127.0.0.1:8000',
    ).split(',')
    if origin.strip()
]
CORS_ALLOW_HEADERS = list(default_headers) + [
    'telegram-init-data',
    'telegram-dev-user',
]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
TELEGRAM_BOT_TOKEN = os.getenv('TOKEN', '')
# Для локальной отладки Mini App вне Telegram (только при DEBUG=True)
TELEGRAM_AUTH_BYPASS = os.getenv('TELEGRAM_AUTH_BYPASS', 'False') == 'True'

# Локалка + туннели: не упираться в CORS / host
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    for host in (
        '.ngrok-free.app',
        '.ngrok.io',
        '.ngrok.app',
        '.trycloudflare.com',
        'localhost',
        '127.0.0.1',
    ):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.import_export',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'adrf',
    'drf_spectacular',
    'corsheaders',
    'import_export',
    'core.apps.CoreConfig',
    'knowledge.apps.KnowledgeConfig',
    'students.apps.StudentsConfig',
    'learning.apps.LearningConfig',
    'bot.apps.BotConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tutor_bot.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tutor_bot.wsgi.application'
ASGI_APPLICATION = 'tutor_bot.asgi.application'

_required_pg = ('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_HOST')
if any(os.getenv(key) in (None, '') for key in _required_pg):
    raise ImproperlyConfigured(
        'PostgreSQL обязателен. Задай POSTGRES_DB, POSTGRES_USER, POSTGRES_HOST в .env '
        '(POSTGRES_PASSWORD можно оставить пустым для локальной разработки).'
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Minsk'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Tutor Bot API',
    'DESCRIPTION': 'API для Telegram-бота подготовки к ЦТ/ЦЭ (Беларусь)',
    'VERSION': '1.0.0',
}

UNFOLD = {
    'SITE_TITLE': 'Tutor Bot',
    'SITE_HEADER': 'Tutor Bot — админка',
    'SITE_SUBHEADER': 'Русский · классы 1–11 · ЦТ/ЦЭ',
    'SITE_SYMBOL': 'school',
    'SHOW_HISTORY': True,
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': 'Быстрый старт',
                'separator': True,
                'collapsible': True,
                'items': [
                    {
                        'title': '📊 Аналитика и Метрики',
                        'icon': 'insights',
                        'link': '/admin/analytics/',
                    },
                    {
                        'title': 'Как устроен контент',
                        'icon': 'menu_book',
                        'link': '/admin/content-guide/',
                    },
                    {
                        'title': 'Задания',
                        'icon': 'quiz',
                        'link': '/admin/knowledge/task/',
                    },
                    {
                        'title': 'Темы по классам',
                        'icon': 'topic',
                        'link': '/admin/knowledge/topic/',
                    },
                    {
                        'title': 'Ученики',
                        'icon': 'group',
                        'link': '/admin/students/student/',
                    },
                ],
            },
        ],
    },
    'COLORS': {
        'primary': {
            '50': '239 246 255',
            '100': '219 234 254',
            '200': '191 219 254',
            '300': '147 197 253',
            '400': '96 165 250',
            '500': '59 130 246',
            '600': '37 99 235',
            '700': '29 78 216',
            '800': '30 64 175',
            '900': '30 58 138',
            '950': '23 37 84',
        },
    },
}

# Celery & Redis settings
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Minsk'

# bePaid Payment Settings (Тестовый магазин 4225)
BEPAID_SHOP_ID = os.getenv('BEPAID_SHOP_ID', '4225')
BEPAID_SECRET_KEY = os.getenv('BEPAID_SECRET_KEY', '3834fbef1fe6ea024ef77f5c79ec7ff1ba710ea6241c08c2f341afda8af4c1c4')
BEPAID_TEST_MODE = os.getenv('BEPAID_TEST_MODE', 'True') == 'True'

# Подробное логирование запросов и ошибок в stdout (для docker logs)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'students': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'knowledge': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'learning': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}



