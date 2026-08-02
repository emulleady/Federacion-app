"""
Django settings for federacion project.
"""

import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------
# BÁSICO
# Local: si no configurás nada, usa estos valores por defecto.
# En Render: se pisan con las variables de entorno reales.
# -------------------------------------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-cambiar-esta-clave-antes-de-produccion')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ('localhost', '127.0.0.1')]

# Render pone la app detrás de un proxy que sí habla HTTPS con el
# navegador, pero internamente reenvía por HTTP. Esta línea le dice a
# Django que confíe en ese header para saber que la conexión es segura
# (sin esto, SECURE_SSL_REDIRECT more abajo generaría un loop infinito).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary',
    'federacion_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # <- sirve el CSS en producción
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'federacion.urls'

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

WSGI_APPLICATION = 'federacion.wsgi.application'

# -------------------------------------------------------------
# BASE DE DATOS
# Local (sin DATABASE_URL): SQLite. En Render: la Postgres del servicio.
# -------------------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

AUTH_USER_MODEL = 'federacion_app.Usuario'

LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------
# ARCHIVOS ESTÁTICOS (CSS) - Whitenoise, siempre local al servidor
# -------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# -------------------------------------------------------------
# ARCHIVOS SUBIDOS (fotos de jugadores, escudos, documentos)
# Si hay credenciales de Cloudinary configuradas, se suben ahí (quedan
# persistentes entre redeploys). Si no, se guardan en el disco local
# (sirve para desarrollo, pero en Render gratis se pierden al redeployar).
# -------------------------------------------------------------
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
}

usa_cloudinary = bool(CLOUDINARY_STORAGE['CLOUD_NAME'])

STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if usa_cloudinary else
            "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# django-cloudinary-storage todavía revisa este nombre viejo (previo al
# diccionario STORAGES de Django 4.2+) durante collectstatic. Sin esto,
# el build se rompe con AttributeError. Es solo un puente de compatibilidad,
# el que realmente manda es STORAGES de arriba.
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]

# Evita que collectstatic falle si algún archivo interno de Django/terceros
# (como un ícono del admin) está referenciado en un CSS pero no se encuentra.
# Solo lo ignora con un aviso, no rompe el deploy.
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -------------------------------------------------------------
# EMAIL - para notificaciones a los delegados
# Local: si no configurás nada, usa los valores de acá abajo.
# En Render: se configuran como variables de entorno (más seguro).
# -------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'tu_cuenta_de_notificaciones@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'la_contraseña_de_aplicacion_de_16_caracteres')
DEFAULT_FROM_EMAIL = f"Federación Fueguina de Futsal <{EMAIL_HOST_USER}>"

# -------------------------------------------------------------
# SEGURIDAD - solo se activa cuando DEBUG=False (o sea, en producción)
# En tu compu local (DEBUG=True) nada de esto molesta, porque no corrés
# HTTPS localmente.
# -------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True          # fuerza HTTPS siempre
    SESSION_COOKIE_SECURE = True        # las cookies de sesión solo viajan por HTTPS
    CSRF_COOKIE_SECURE = True           # la cookie CSRF solo viaja por HTTPS
    SECURE_HSTS_SECONDS = 31536000      # le dice al navegador "solo HTTPS por 1 año"
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True  # evita que el navegador "adivine" tipos de archivo
    X_FRAME_OPTIONS = 'DENY'            # evita que la app se pueda embeber en un iframe ajeno
