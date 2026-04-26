"""
Django settings for rdash-webhook-service.

Clean Architecture structure:
- domain/     : Pure Python, zero framework dependencies
- interface/  : Django-specific entry points (views, serializers, urls, tasks)
- data/       : Infrastructure implementations (models, repositories, gateways)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-in-production')

DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    # Django built-in apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',

    # Local apps (Clean Architecture)
    'data.models.apps.DataModelsConfig',
    'interface.apps.InterfaceConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =============================================================================
# DATABASE - PostgreSQL (with SQLite fallback for local dev)
# =============================================================================

# Check if we should use SQLite (for local development without Docker)
USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() == 'true'

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'rdash_webhooks'),
            'USER': os.getenv('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 60,  # Connection pooling
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES
# =============================================================================

STATIC_URL = 'static/'

# =============================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'interface.authentication.APIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'interface.exceptions.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

# Redis as message broker
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Task settings
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Task execution settings
CELERY_TASK_ACKS_LATE = True  # Acknowledge after task completes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Prevent worker from grabbing too many tasks
CELERY_TASK_TIME_LIMIT = 300  # Hard timeout (5 minutes)
CELERY_TASK_SOFT_TIME_LIMIT = 240  # Soft timeout (4 minutes)
CELERY_TASK_DEFAULT_QUEUE = os.getenv('CELERY_TASK_DEFAULT_QUEUE', 'webhooks.default')
CELERY_TASK_ROUTES = {
    'interface.tasks.dispatch_outbox_batch': {'queue': 'webhooks.outbox'},
    'interface.tasks.fanout_event': {'queue': 'webhooks.fanout'},
    'interface.tasks.deliver_webhook': {'queue': 'webhooks.delivery'},
}
CELERY_TASK_ANNOTATIONS = {
    'interface.tasks.deliver_webhook': {
        'rate_limit': os.getenv('WEBHOOK_DELIVERY_RATE_LIMIT', '120/m'),
    },
}
CELERY_BEAT_SCHEDULE = {
    'dispatch-webhook-outbox': {
        'task': 'interface.tasks.dispatch_outbox_batch',
        'schedule': float(os.getenv('WEBHOOK_OUTBOX_DISPATCH_INTERVAL_SECONDS', '5.0')),
    },
}

# Retry settings
CELERY_TASK_DEFAULT_RETRY_DELAY = 60
CELERY_TASK_MAX_RETRIES = 3

# =============================================================================
# WEBHOOK DELIVERY SETTINGS
# =============================================================================

# HTTP Gateway timeouts (strict for event-driven systems)
WEBHOOK_CONNECT_TIMEOUT = int(os.getenv('WEBHOOK_CONNECT_TIMEOUT', '5'))  # seconds
WEBHOOK_READ_TIMEOUT = int(os.getenv('WEBHOOK_READ_TIMEOUT', '15'))  # seconds

# Retry policy
WEBHOOK_MAX_RETRIES = int(os.getenv('WEBHOOK_MAX_RETRIES', '5'))
WEBHOOK_BASE_RETRY_DELAY = float(os.getenv('WEBHOOK_BASE_RETRY_DELAY', '1.0'))  # seconds
WEBHOOK_MAX_RETRY_DELAY = float(os.getenv('WEBHOOK_MAX_RETRY_DELAY', '60.0'))  # seconds
WEBHOOK_RETRY_JITTER = float(os.getenv('WEBHOOK_RETRY_JITTER', '0.1'))  # jitter factor

# Fan-out settings
WEBHOOK_FANOUT_BATCH_SIZE = int(os.getenv('WEBHOOK_FANOUT_BATCH_SIZE', '100'))
WEBHOOK_OUTBOX_DISPATCH_BATCH_SIZE = int(os.getenv('WEBHOOK_OUTBOX_DISPATCH_BATCH_SIZE', '100'))
WEBHOOK_OUTBOX_STALE_LOCK_SECONDS = int(os.getenv('WEBHOOK_OUTBOX_STALE_LOCK_SECONDS', '300'))
WEBHOOK_OUTBOX_BASE_RETRY_DELAY = float(os.getenv('WEBHOOK_OUTBOX_BASE_RETRY_DELAY', '1.0'))
WEBHOOK_OUTBOX_MAX_RETRY_DELAY = float(os.getenv('WEBHOOK_OUTBOX_MAX_RETRY_DELAY', '60.0'))
WEBHOOK_TENANT_QUEUE_BUCKETS = int(os.getenv('WEBHOOK_TENANT_QUEUE_BUCKETS', '16'))
WEBHOOK_SECRET_ENCRYPTION_KEY = os.getenv('WEBHOOK_SECRET_ENCRYPTION_KEY', '')

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'webhook-service.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': os.getenv('CELERY_LOG_LEVEL', 'INFO'),
        },
        'webhook': {
            'handlers': ['console', 'file'],
            'level': os.getenv('WEBHOOK_LOG_LEVEL', 'DEBUG'),
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)
