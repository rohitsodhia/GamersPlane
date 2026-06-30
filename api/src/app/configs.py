import os
from typing import Literal


class ConfigStore:
    def __init__(self):
        self.LOGIN_COOKIE = "loginHash"
        self._from_env()
        self.AVATARS_ROOT = self.IMAGES_HOST_NAME + "/avatars"

    def _from_env(self):
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
        self.TZ = os.getenv("TZ", "UTC")

        self.HOST_NAME = os.getenv("HOST_NAME", "")
        self.V1_HOST_NAME = os.getenv("V1_HOST_NAME", "")
        self.API_HOST_NAME = os.getenv("API_HOST_NAME", "")
        self.IMAGES_HOST_NAME = os.getenv("IMAGES_HOST_NAME", "")
        self.COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")
        self.ROOT_DIR = os.getenv("ROOT_DIR", "")

        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
        self.PVAR = os.getenv("PVAR", "")

        self.PAGINATE_PER_PAGE = int(os.getenv("PAGINATE_PER_PAGE", 20))

        dialect = os.getenv("DATABASE_DIALECT", "postgresql")
        self.DATABASE_DIALECT: Literal["postgresql", "mysql"] = self._get_dialect(
            dialect
        )
        self.DATABASE_HOST = os.getenv("DATABASE_HOST", "postgres")
        self.DATABASE_PORT = int(os.getenv("DATABASE_PORT", 5432))
        self.DATABASE_USER = os.getenv("DATABASE_USER", "gamersplane")
        self.DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "test123")
        self.DATABASE_DATABASE = os.getenv("DATABASE_DATABASE", "gamersplane")
        self.DATABASE_SSH_USERNAME = os.getenv("DATABASE_SSH_USERNAME", None)
        self.DATABASE_SSH_PKEY = "/ssh_key"

        legacy_dialect = os.getenv("LEGACY_DATABASE_DIALECT", "mysql")
        self.LEGACY_DATABASE_DIALECT: Literal["postgresql", "mysql"] = (
            self._get_dialect(legacy_dialect)
        )
        self.LEGACY_DATABASE_HOST = os.getenv("LEGACY_DATABASE_HOST", "mysql")
        self.LEGACY_DATABASE_PORT = int(os.getenv("LEGACY_DATABASE_PORT", 3306))
        self.LEGACY_DATABASE_USER = os.getenv("LEGACY_DATABASE_USER", "gamersplane")
        self.LEGACY_DATABASE_PASSWORD = os.getenv("LEGACY_DATABASE_PASSWORD", "test123")
        self.LEGACY_DATABASE_DATABASE = os.getenv(
            "LEGACY_DATABASE_DATABASE", "gamersplane"
        )
        self.LEGACY_DATABASE_SSH_USERNAME = os.getenv(
            "LEGACY_DATABASE_SSH_USERNAME", None
        )
        self.LEGACY_DATABASE_SSH_PKEY = "/legacy_ssh_key"

    def _get_dialect(self, dialect: str) -> Literal["postgresql"] | Literal["mysql"]:
        if dialect == "postgresql":
            return "postgresql"
        elif dialect == "mysql":
            return "mysql"
        else:
            raise ValueError("DATABASE_DIALECT must be either 'postgresql' or 'mysql'")


configs = ConfigStore()
