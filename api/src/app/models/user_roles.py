from typing import TYPE_CHECKING

from models.base import Base, SoftDeleteMixin, TimestampMixin
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class UserRoles(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
