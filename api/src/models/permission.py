from enum import Enum
from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models import Role


class ValidPermissions(Enum):
    ROLE_ADMIN = "role_admin_{role_id}"


class Permission(Base):
    __tablename__ = "permissions"

    permission: Mapped[str] = mapped_column(String(64), primary_key=True)

    roles: Mapped[List["Role"]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )

    def __init__(self, *args, **kwargs) -> None:
        self._valid_permission = False
        super().__init__(*args, **kwargs)

    def set_permission(self, permission: ValidPermissions, **kwargs) -> None:
        if type(permission) is not ValidPermissions:
            raise ValueError(f"'{permission}' is not a ValidPermission")

        if "{" in permission.value:
            self.permission = permission.value.format(**kwargs)
        else:
            self.permission = permission.value
