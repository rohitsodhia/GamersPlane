import envs
from django_apps import apps


def make_key(key, key_prefix, version):
    return key


SECRET_KEY = envs.DJANGO_SECRET_KEY
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": envs.POSTGRES_DATABASE,
        "USER": envs.POSTGRES_USER,
        "PASSWORD": envs.POSTGRES_PASSWORD,
        "HOST": "postgres",
        "PORT": "5432",
    }
}
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": envs.REDIS_HOST,
        "TIMEOUT": envs.REDIS_TTL,
        "OPTIONS": {
            "MAX_ENTRIES": 1000000,
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_FUNCTION": make_key,
    }
}
INSTALLED_APPS = apps + ["django_extensions"]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = False
