from django_apps import apps


DATABASES = {"default": {"ENGINE": "django.db.backends.mysql", "NAME": "gamersplane"}}
INSTALLED_APPS = apps
SECRET_KEY = "asdf"
