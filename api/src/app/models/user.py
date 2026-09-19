from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import bcrypt
import jwt
from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship

from app.configs import configs
from app.models.base import Base
from app.models.rbac import RolePermission
from app.models.user_meta import UserMeta
from app.schemas import ErrorItem

if TYPE_CHECKING:
    from app.models import Role


class User(MappedAsDataclass, AsyncAttrs, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    username: Mapped[str] = mapped_column(String(24), unique=True)
    password: Mapped[str] = mapped_column(String(64), init=False)
    email: Mapped[str] = mapped_column(String(50), unique=True)
    join_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now(), init=False
    )
    activated_on: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, init=False
    )
    last_activity: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, init=False
    )
    suspended_until: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, init=False
    )
    banned: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, init=False
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="user_roles", back_populates="users", default_factory=list
    )
    meta: Mapped[list[UserMeta]] = relationship(default_factory=list)

    MIN_PASSWORD_LENGTH: int = 8

    # @property
    # def permissions(self) -> list[int]:
    #     with connection.cursor() as cursor:
    #         cursor.execute(
    #             "SELECT DISTINCT permission FROM permissions p INNER JOIN role_permissions rp ON rp.permissionId = p.id INNER JOIN roles r ON r.id = rp.roleId INNER JOIN user_roles ur ON ur.roleId = r.id WHERE ur.userId = %s",
    #             [self.id],
    #         )
    #         permissions = cursor.fetchall()
    #     return list([v[0] for v in permissions])

    @staticmethod
    def validate_password(password: str) -> list[ErrorItem]:
        invalid: list[ErrorItem] = []
        if len(password) < User.MIN_PASSWORD_LENGTH:
            invalid.append(
                ErrorItem(code="pass_too_short", detail="Password too short")
            )
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

    def login_block(self) -> str | None:
        """Why this user may not hold an authenticated session, or ``None``.

        ``"banned"`` is permanent; ``"suspended"`` lasts until ``suspended_until``
        (a past timestamp no longer blocks). Checked both at ``/auth/login`` and
        on every authenticated request by ``app.middleware.check_authorization``.
        """
        if self.banned is not None:
            return "banned"
        if (
            self.suspended_until is not None
            and self.suspended_until > datetime.datetime.now(datetime.timezone.utc)
        ):
            return "suspended"
        return None

    def generate_jwt(self, exp_len: dict | None = None) -> str:
        if not exp_len:
            exp_len = {"weeks": 2}
        return jwt.encode(
            {
                "user_id": self.id,
                "exp": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(**exp_len),
            },
            configs.JWT_SECRET_KEY,
            algorithm=configs.JWT_ALGORITHM,
        )

    @property
    def global_permissions(self) -> set[str]:
        """Permission verbs granted to this user at global scope (scope_type IS NULL).

        A global ``deny`` for a verb overrides any global ``allow`` for it. Scoped
        grants (forum/role) are ignored here — those resolve per-resource elsewhere.
        """
        allowed: set[str] = set()
        denied: set[str] = set()
        for role in self.roles:
            for grant in role.grants:
                if grant.scope_type is not None:
                    continue
                verb = grant.permission.value
                if grant.effect is RolePermission.Effects.DENY:
                    denied.add(verb)
                else:
                    allowed.add(verb)
        return allowed - denied

    def has_global_permission(self, *verbs: str) -> bool:
        """True if the user holds any of ``verbs`` at global scope.

        Holding the ``admin`` verb satisfies any check, mirroring ``ADMIN_OVERRIDE``
        in ``app.middleware``.
        """
        held = self.global_permissions
        if RolePermission.ValidPermissions.ADMIN.value in held:
            return True
        return not held.isdisjoint(verbs)

    @property
    def avatar(self) -> str:
        for meta in self.meta:
            if meta.key == UserMeta.MetaKeys.AVATAR_EXT.value:
                return f"{self.id}.{meta.value}"
        return "avatar.png"

    @property
    def avatar_url(self) -> str:
        return f"{configs.AVATARS_ROOT}/users/{self.avatar}"
