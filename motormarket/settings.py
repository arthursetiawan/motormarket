from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'byz13640969420'

# Load .env file for local development
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Allow SECRET_KEY and DEBUG to be overridden from environment
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)
DEBUG = bool(int(os.environ.get('DEBUG', '1')))

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'market',
    'rest_framework',
    'corsheaders',
    'sorl.thumbnail',  # Added optional thumbnailing app
    'channels',  # Added Channels app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

ROOT_URLCONF = 'motormarket.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'motormarket.wsgi.application'
ASGI_APPLICATION = 'motormarket.asgi.application'  # Added ASGI application

DATABASES = {
    'default': dj_database_url.config(default='sqlite:///{}'.format(os.path.join(BASE_DIR, 'db.sqlite3')))
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Jakarta'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Static files (for collectstatic)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
# Optionally configure external storage using environment variables (S3-compatible)
USE_S3 = os.environ.get('USE_S3', '')
if USE_S3:
    # django-storages settings for S3-compatible storage
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL')  # for DigitalOcean/Wasabi/MinIO
else:
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

SITE_ID = 1

CRISPY_TEMPLATE_PACK = 'bootstrap4'

CORS_ALLOW_ALL_ORIGINS = True

# Channels (WebSocket) configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.environ.get('REDIS_URL', 'redis://localhost:6379')],
        },
    },
}

# Redirects for login/logout (avoid default /accounts/profile/ 404)
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
# allauth specific
ACCOUNT_ADAPTER = 'allauth.account.adapter.DefaultAccountAdapter'
ACCOUNT_LOGOUT_REDIRECT = '/'

# REST framework defaults
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
}

# NegoMotor platform fee (buyer success fee) — tweak via env without code changes
PLATFORM_FEE_RATE = os.environ.get("PLATFORM_FEE_RATE", "0.03")
PLATFORM_FEE_MIN_IDR = os.environ.get("PLATFORM_FEE_MIN_IDR", "150000")
PLATFORM_FEE_MAX_IDR = os.environ.get("PLATFORM_FEE_MAX_IDR", "2500000")
PLATFORM_FEE_SIMULATED = bool(int(os.environ.get("PLATFORM_FEE_SIMULATED", "1")))
