from __future__ import annotations

from enum import Enum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.helpers.enums import LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


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
