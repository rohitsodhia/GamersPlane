from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.helpers.functions import pluralize
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import User


class Permission(Base):
    class ValidPermissions(LabelEnum):
        # value, label. Action verbs only — what a grant applies to (a forum, a role)
        # is carried by RolePermission.scope_type / scope_id, never baked into the string.
        ADMIN = "admin", "Administrator"
        ACP_ACCESS = "access_acp", "Access ACP"
        ROLE_ADMIN = "role_admin", "Manage Role"
        FORUM_ACCESS = "access_forum", "View Forum"
        FORUM_MODERATE = "moderate_forum", "Moderate Forum"

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), unique=True)
    roles: Mapped[list["Role"]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )


class Role(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    _name: Mapped[str] = mapped_column("name", String(64), unique=True)
    _plural: Mapped[str] = mapped_column("plural", String(64), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped[User] = relationship()
    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )

    @hybrid_property
    def name(self):
        return self._name

    @name.inplace.setter
    def set_name(self, value):
        self._name = value
        self._plural = pluralize(self._name)

    @hybrid_property
    def plural(self):
        return self._plural


class RolePermission(Base, TimestampMixin, SoftDeleteMixin):
    class Effects(str, Enum):
        ALLOW = "allow"
        DENY = "deny"

    class ScopeTypes(str, Enum):
        FORUM = "forum"
        ROLE = "role"

    __tablename__ = "role_permissions"
    __table_args__ = (
        # One grant per (role, permission, scoped resource). NULLS NOT DISTINCT so a
        # role can't hold two conflicting global grants for the same permission.
        UniqueConstraint(
            "role_id",
            "permission_id",
            "scope_type",
            "scope_id",
            name="uq_role_permissions_grant",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"))
    # scope_type/scope_id bind the grant to one resource (e.g. forum 4). Both NULL
    # means the grant is global (e.g. access_acp).
    scope_type: Mapped[ScopeTypes | None] = mapped_column(
        LabelEnumType(ScopeTypes, String(16)), nullable=True
    )
    scope_id: Mapped[int | None] = mapped_column(nullable=True)
    effect: Mapped[Effects] = mapped_column(
        LabelEnumType(Effects, String(8)), default=Effects.ALLOW
    )


class UserRole(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
