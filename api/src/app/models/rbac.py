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


class Role(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    _name: Mapped[str] = mapped_column("name", String(64), unique=True)
    _plural: Mapped[str] = mapped_column("plural", String(64), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped[User] = relationship()
    grants: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )

    def grant(
        self,
        permission: "RolePermission.ValidPermissions",
        *,
        scope_type: "RolePermission.ScopeTypes | None" = None,
        scope_id: int | None = None,
        effect: "RolePermission.Effects | None" = None,
    ) -> "RolePermission":
        """Attach a permission grant to this role.

        Defaults to a global (unscoped) `allow`. Pass ``scope_type``/``scope_id``
        to bind the grant to one resource, and ``effect`` to make it a deny.
        """
        rp = RolePermission(
            permission=permission,
            scope_type=scope_type,
            scope_id=scope_id,
            effect=effect or RolePermission.Effects.ALLOW,
        )
        self.grants.append(rp)
        return rp

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
    class ValidPermissions(LabelEnum):
        # value, label. Action verbs only — what a grant applies to (a forum, a role)
        # is carried by RolePermission.scope_type / scope_id, never baked into the string.
        ADMIN = "admin", "Administrator"
        ACP_ACCESS = "access_acp", "Access ACP"
        ROLE_ADMIN = "role_admin", "Manage Role"
        FORUM_ACCESS = "access_forum", "View Forum"
        FORUM_MODERATE = "moderate_forum", "Moderate Forum"

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
            "permission",
            "scope_type",
            "scope_id",
            name="uq_role_permissions_grant",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    role: Mapped["Role"] = relationship(back_populates="grants")
    permission: Mapped[ValidPermissions] = mapped_column(
        LabelEnumType(ValidPermissions, String(64))
    )
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
