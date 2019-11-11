import django
from django.conf import settings

from django_apps import apps


settings.configure(
    DATABASES={
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "test_gamersplane"}
    },
    INSTALLED_APPS=apps,
)
django.setup()