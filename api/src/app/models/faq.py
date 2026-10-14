from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, TimestampMixin


class FAQ(Base, TimestampMixin):
    class Categories(LabelEnum):
        # Declaration order is the display order.
        GETTING_STARTED = "getting-started", "Getting Started"
        CHARACTERS = "characters", "Characters"
        GAMES = "games", "Games"
        TOOLS = "tools", "Tools"

    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[Categories] = mapped_column(
        LabelEnumType(Categories, String(20)), index=True
    )
    question: Mapped[str]
    # ProseMirror/Tiptap document.
    answer: Mapped[dict] = mapped_column(JSON())
    # Position within the category, starting at 1.
    order: Mapped[int]
