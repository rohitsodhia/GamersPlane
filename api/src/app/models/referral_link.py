from models.base import Base, SoftDeleteMixin
from sqlalchemy.orm import Mapped, mapped_column


class ReferralLink(Base, SoftDeleteMixin):
    __tablename__ = "referral_links"

    key: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    link: Mapped[str]
    order: Mapped[int] = mapped_column(unique=True)
    enabled: Mapped[bool] = mapped_column(default=True)
