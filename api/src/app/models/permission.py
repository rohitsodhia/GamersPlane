from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum
from app.models.base import Base

if TYPE_CHECKING:
    from app.models import Role


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
