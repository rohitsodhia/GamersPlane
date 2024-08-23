import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

HOST_NAME = os.getenv("HOST_NAME")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_TTL = os.getenv("REDIS_TTL")

DJANGO_SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

EMAIL_URI = os.getenv("EMAIL_URI")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_LOGIN = os.getenv("EMAIL_LOGIN")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
