import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

HOST_NAME = os.getenv("HOST_NAME")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_DATABASE = os.getenv("DATABASE_DATABASE")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_TTL = os.getenv("REDIS_TTL")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

EMAIL_URI = os.getenv("EMAIL_URI")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_LOGIN = os.getenv("EMAIL_LOGIN")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
