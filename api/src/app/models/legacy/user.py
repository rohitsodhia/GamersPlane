import datetime
import hashlib
from typing import TYPE_CHECKING, List

from fastapi import Response
from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship

from app.configs import configs
from app.models.legacy.base import LegacyBase
from app.util import random_alpha_num

if TYPE_CHECKING:
    from app.models.legacy import UserMeta


class User(MappedAsDataclass, AsyncAttrs, LegacyBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column("userID", primary_key=True, init=False)
    username: Mapped[str] = mapped_column(String(24), unique=True)
    password: Mapped[str] = mapped_column(String(64), init=False)
    salt: Mapped[str] = mapped_column(String(20), init=False)
    email: Mapped[str] = mapped_column(String(50), unique=True)
    join_date: Mapped[datetime.datetime] = mapped_column(
        "joinDate", DateTime(timezone=True), insert_default=func.now(), init=False
    )
    activated_on: Mapped[datetime.datetime] = mapped_column(
        "activatedOn", DateTime(timezone=True), nullable=True, init=False
    )
    last_activity: Mapped[datetime.datetime] = mapped_column(
        "lastActivity", DateTime(timezone=True), nullable=True, init=False
    )
    timezone: Mapped[str] = mapped_column(String(20), nullable=True)
    suspended_until: Mapped[datetime.datetime] = mapped_column(
        "suspendedUntil", DateTime(timezone=True), nullable=True, init=False
    )
    banned: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, init=False
    )
    meta: Mapped[List["UserMeta"]] = relationship(default_factory=list)

    MIN_PASSWORD_LENGTH: int = 6

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

    def hash_password(self, password: str) -> str:
        self.salt = random_alpha_num(20)
        hash_str = configs.PVAR + password + self.salt
        return hashlib.sha256(hash_str.encode()).hexdigest()

    def set_password(self, password: str) -> bool:
        pass_valid = User.validate_password(password)
        if pass_valid == []:
            self.password = self.hash_password(password)
            return True
        return False

    def activate(self) -> None:
        self.activated_on = datetime.datetime.now(datetime.timezone.utc)

    def check_pass(self, password: str) -> bool:
        encoded_password = (configs.PVAR + password + self.salt).encode("utf-8")
        encrypted_password = hashlib.sha256(encoded_password).hexdigest()
        return encrypted_password == self.password

    def set_cookies(self, response: Response):
        secure: bool = configs.ENVIRONMENT != "dev"
        response.delete_cookie(
            "loginHash",
            domain=configs.COOKIE_DOMAIN,
            secure=secure,
            httponly=True,
        )
        encoded_hash = (
            configs.PVAR + self.email + self.join_date.strftime("%Y-%m-%d %H:%M:%S")
        ).encode("utf-8")
        encrypted_hash = hashlib.sha256(encoded_hash).hexdigest()
        response.set_cookie(
            "loginHash",
            encrypted_hash,
            (60 * 60 * 24 * 7),
            domain=configs.COOKIE_DOMAIN,
            secure=secure,
            httponly=True,
        )

        return response
