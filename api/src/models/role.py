from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.functions import pluralize
from models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from models import Permission, User


class Role(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    _name: Mapped[str] = mapped_column("name", String(64), unique=True)
    _plural: Mapped[str] = mapped_column("plural", String(64), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    permissions: Mapped[List["Permission"]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )
    users: Mapped[List["User"]] = relationship(
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
