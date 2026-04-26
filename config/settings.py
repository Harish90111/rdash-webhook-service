"""
Django settings for rdash-webhook-service.

Clean Architecture structure:
- domain/     : Pure Python, zero framework dependencies
- interface/  : Django-specific entry points (views, serializers, urls, tasks)
- data/       : Infrastructure implementations (models, repositories, gateways)
"""

from importlib.util import find_spec
from pathlib import Path

from dotenv import load_dotenv

from config.env import (
    DEFAULT_DEV_SECRET_KEY,
    VALID_APP_ENVS,
    build_celery_beat_schedule,
    build_celery_task_annotations,
    build_celery_transport_options,
    build_database_settings,
    env_bool,
    env_choice,
    env_float,
    env_int,
    env_list,
    env_str,
    validate_runtime_settings,
)

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

APP_ENV = env_choice("APP_ENV", "development", choices=VALID_APP_ENVS)
DEBUG = env_bool("DEBUG", APP_ENV != "production")
SECRET_KEY = env_str("DJANGO_SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "[::1]"] if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])
validate_runtime_settings(
    app_env=APP_ENV,
    secret_key=SECRET_KEY,
    allowed_hosts=ALLOWED_HOSTS,
)

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

HAS_DRF_SPECTACULAR = find_spec("drf_spectacular") is not None

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
if HAS_DRF_SPECTACULAR:
    INSTALLED_APPS.append('drf_spectacular')

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

USE_SQLITE = env_bool("USE_SQLITE", False)
DATABASES = build_database_settings(BASE_DIR, use_sqlite=USE_SQLITE)

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
if HAS_DRF_SPECTACULAR:
    REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'

# =============================================================================
# SPECTACULAR SETTINGS (OpenAPI/Swagger)
# =============================================================================

if HAS_DRF_SPECTACULAR:
    SPECTACULAR_SETTINGS = {
        'TITLE': 'Webhook Delivery Service API',
        'DESCRIPTION': 'Event-driven webhook delivery service with subscription management and reliable fan-out delivery.',
        'VERSION': '1.0.0',
        'SERVE_PERMISSIONS': [
            'rest_framework.permissions.AllowAny',  # Allow unauthenticated access to schema
        ],
        'CONTACT': {
            'name': 'Development Team',
            'email': 'support@example.com',
        },
        'LICENSE': {
            'name': 'Proprietary',
        },
        'SERVERS': [
            {'url': 'http://localhost:8000', 'description': 'Development'},
            {'url': 'https://api.example.com', 'description': 'Production'},
        ] if DEBUG else [
            {'url': 'https://api.example.com', 'description': 'Production'},
        ],
        'SCHEMA_PATH_PREFIX': '/api/',
        'COMPONENT_SPLIT_REQUEST': True,
        'SORT_OPERATIONS_BY_NAME': True,
    }

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

# Redis as message broker
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = env_bool(
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
    True,
)
CELERY_BROKER_POOL_LIMIT = env_int("CELERY_BROKER_POOL_LIMIT", 10, minimum=0)
CELERY_BROKER_HEARTBEAT = env_int("CELERY_BROKER_HEARTBEAT", 30, minimum=0)
CELERY_BROKER_TRANSPORT_OPTIONS = build_celery_transport_options()

# Task settings
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = env_bool("CELERY_TASK_TRACK_STARTED", True)

# Task execution settings
CELERY_TASK_ACKS_LATE = True  # Acknowledge after task completes
CELERY_WORKER_PREFETCH_MULTIPLIER = env_int(
    "CELERY_WORKER_PREFETCH_MULTIPLIER",
    1,
    minimum=1,
)  # Prevent worker from grabbing too many tasks
CELERY_WORKER_CONCURRENCY = env_int(
    "CELERY_WORKER_CONCURRENCY",
    2 if DEBUG else 4,
    minimum=1,
)
CELERY_WORKER_MAX_TASKS_PER_CHILD = env_int(
    "CELERY_WORKER_MAX_TASKS_PER_CHILD",
    500,
    minimum=1,
)
CELERY_WORKER_MAX_MEMORY_PER_CHILD = env_int(
    "CELERY_WORKER_MAX_MEMORY_PER_CHILD",
    0,
    minimum=0,
)
CELERY_WORKER_SEND_TASK_EVENTS = env_bool("CELERY_WORKER_SEND_TASK_EVENTS", False)
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 300, minimum=1)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 240, minimum=1)
CELERY_TASK_DEFAULT_QUEUE = env_str("CELERY_TASK_DEFAULT_QUEUE", "webhooks.default")
CELERY_TASK_ROUTES = {
    'interface.tasks.dispatch_outbox_batch': {'queue': 'webhooks.outbox'},
    'interface.tasks.fanout_event': {'queue': 'webhooks.fanout'},
    'interface.tasks.deliver_webhook': {'queue': 'webhooks.delivery'},
}
CELERY_TASK_ANNOTATIONS = build_celery_task_annotations()
CELERY_BEAT_SCHEDULE = build_celery_beat_schedule()
CELERY_BEAT_MAX_LOOP_INTERVAL = env_int("CELERY_BEAT_MAX_LOOP_INTERVAL", 30, minimum=1)

# Retry settings
CELERY_TASK_DEFAULT_RETRY_DELAY = env_int("CELERY_TASK_DEFAULT_RETRY_DELAY", 60, minimum=0)
CELERY_TASK_MAX_RETRIES = env_int("CELERY_TASK_MAX_RETRIES", 3, minimum=0)

# =============================================================================
# WEBHOOK DELIVERY SETTINGS
# =============================================================================

# HTTP Gateway timeouts (strict for event-driven systems)
WEBHOOK_CONNECT_TIMEOUT = env_int("WEBHOOK_CONNECT_TIMEOUT", 5, minimum=1)  # seconds
WEBHOOK_READ_TIMEOUT = env_int("WEBHOOK_READ_TIMEOUT", 15, minimum=1)  # seconds

# Retry policy
WEBHOOK_MAX_RETRIES = env_int("WEBHOOK_MAX_RETRIES", 5, minimum=0)
WEBHOOK_BASE_RETRY_DELAY = env_float("WEBHOOK_BASE_RETRY_DELAY", 1.0, minimum=0.0)  # seconds
WEBHOOK_MAX_RETRY_DELAY = env_float("WEBHOOK_MAX_RETRY_DELAY", 60.0, minimum=0.0)  # seconds
WEBHOOK_RETRY_JITTER = env_float("WEBHOOK_RETRY_JITTER", 0.1, minimum=0.0)  # jitter factor

# Fan-out settings
WEBHOOK_FANOUT_BATCH_SIZE = env_int("WEBHOOK_FANOUT_BATCH_SIZE", 100, minimum=1)
WEBHOOK_OUTBOX_DISPATCH_BATCH_SIZE = env_int("WEBHOOK_OUTBOX_DISPATCH_BATCH_SIZE", 100, minimum=1)
WEBHOOK_OUTBOX_STALE_LOCK_SECONDS = env_int("WEBHOOK_OUTBOX_STALE_LOCK_SECONDS", 300, minimum=1)
WEBHOOK_OUTBOX_BASE_RETRY_DELAY = env_float("WEBHOOK_OUTBOX_BASE_RETRY_DELAY", 1.0, minimum=0.0)
WEBHOOK_OUTBOX_MAX_RETRY_DELAY = env_float("WEBHOOK_OUTBOX_MAX_RETRY_DELAY", 60.0, minimum=0.0)
WEBHOOK_TENANT_QUEUE_BUCKETS = env_int("WEBHOOK_TENANT_QUEUE_BUCKETS", 16, minimum=1)
WEBHOOK_SECRET_ENCRYPTION_KEY = env_str("WEBHOOK_SECRET_ENCRYPTION_KEY", "")

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
            '()': 'config.logging.StructuredJSONFormatter',
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
            'maxBytes': env_int("LOG_FILE_MAX_BYTES", 1024 * 1024 * 10, minimum=1),
            'backupCount': env_int("LOG_FILE_BACKUP_COUNT", 5, minimum=1),
            'formatter': 'json',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': env_str("DJANGO_LOG_LEVEL", "INFO"),
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': env_str("CELERY_LOG_LEVEL", "INFO"),
        },
        'webhook': {
            'handlers': ['console', 'file'],
            'level': env_str("WEBHOOK_LOG_LEVEL", "DEBUG"),
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)
