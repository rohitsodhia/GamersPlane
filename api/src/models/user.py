import datetime
from typing import TYPE_CHECKING, List, Optional

import bcrypt
import jwt
from sqlalchemy import DateTime, String, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import session_manager
from envs import JWT_ALGORITHM, JWT_SECRET_KEY
from models.base import Base

if TYPE_CHECKING:
    from models import Role, UserMeta


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(24), unique=True)
    password: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(50), unique=True)
    join_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    activated_on: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_until: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    banned: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    roles: Mapped[List["Role"]] = relationship(
        secondary="user_roles", back_populates="users"
    )
    admin: Mapped[bool] = mapped_column(default=False)
    meta: Mapped[List["UserMeta"]] = relationship()

    MIN_PASSWORD_LENGTH: int = 8

    @staticmethod
    async def get(user_id: Optional[int] = None) -> Optional["User"]:
        async with session_manager.session() as db_session:
            user = await db_session.scalar(
                select(User).where(User.id == user_id).limit(1)
            )
            return user

    # @property
    # def permissions(self) -> List[int]:
    #     with connection.cursor() as cursor:
    #         cursor.execute(
    #             "SELECT DISTINCT permission FROM permissions p INNER JOIN role_permissions rp ON rp.permissionId = p.id INNER JOIN roles r ON r.id = rp.roleId INNER JOIN user_roles ur ON ur.roleId = r.id WHERE ur.userId = %s",
    #             [self.id],
    #         )
    #         permissions = cursor.fetchall()
    #     return list([v[0] for v in permissions])

    @staticmethod
    def validate_password(password: str) -> list[str]:
        invalid: list[str] = []
        if len(password) < User.MIN_PASSWORD_LENGTH:
            invalid.append("pass_too_short")
        return invalid

    @staticmethod
    def hash_password(password: str) -> str:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        return hashed.decode("utf-8")

    def set_password(self, password: str) -> bool:
        pass_valid = User.validate_password(password)
        if pass_valid == []:
            self.password = self.hash_password(password)
            return True
        return False

    def activate(self) -> None:
        self.activated_on = datetime.datetime.now(datetime.timezone.utc)

    def check_pass(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.password.encode("utf-8"))

    def generate_jwt(self, exp_len: Optional[dict] = None) -> str:
        if not exp_len:
            exp_len = {"weeks": 2}
        return jwt.encode(
            {
                "user_id": self.id,
                "exp": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(**exp_len),
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
