import os
from typing import Literal


class ConfigStore:
    def from_env(self):
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

        self.HOST_NAME = os.getenv("HOST_NAME", "")
        self.API_HOST_NAME = os.getenv("API_HOST_NAME", "")
        self.ROOT_DIR = os.getenv("ROOT_DIR", "")

        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

        self.PAGINATE_PER_PAGE = int(os.getenv("PAGINATE_PER_PAGE", 20))

        dialect = os.getenv("DATABASE_DIALECT", "postgresql")
        self.DATABASE_DIALECT: Literal["postgresql", "mysql"] = self._get_dialect(
            dialect
        )
        self.DATABASE_HOST = os.getenv("DATABASE_HOST", "postgres")
        self.DATABASE_USER = os.getenv("DATABASE_USER", "shopping")
        self.DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "test123")
        self.DATABASE_DATABASE = os.getenv("DATABASE_DATABASE", "shopping")

    def _get_dialect(self, dialect: str) -> Literal["postgresql"] | Literal["mysql"]:
        if dialect == "postgresql":
            return "postgresql"
        elif dialect == "mysql":
            return "mysql"
        else:
            raise ValueError("DATABASE_DIALECT must be either 'postgresql' or 'mysql'")


configs = ConfigStore()
configs.from_env()
