from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin


class ReferralLink(Base, SoftDeleteMixin):
    __tablename__ = "referral_links"

    key: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    link: Mapped[str]
    order: Mapped[int] = mapped_column(unique=True)
    enabled: Mapped[bool] = mapped_column(default=True)
