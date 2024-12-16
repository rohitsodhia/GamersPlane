from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func, select
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship

from database import session_manager
from helpers.enums import LabelEnum
from models.base import Base, TimestampMixin
from models.user import User


class Token(Base, TimestampMixin):
    class TokenTypes(LabelEnum):
        ACCOUNT_ACTIVATION = "aa", "Account Activation"
        PASSWORD_RESET = "pr", "Password Reset"

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship()
    token_type: Mapped[TokenTypes] = mapped_column(String(2))
    token: Mapped[UUID] = mapped_column(Uuid(), default=uuid4)
    requested_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __mapper_args__ = {
        "polymorphic_on": "token_type",
        "polymorphic_abstract": True,
    }

    @staticmethod
    async def validate_token(token: str, email: Optional[str] = None) -> "Token | None":
        async with session_manager.session() as db_session:
            get_token_query = (
                select(Token)
                .options(joinedload(Token.user))
                .where(Token.token == token)
                .limit(1)
            )
            if email:
                get_token_query = get_token_query.join(Token.user).where(
                    User.email == email
                )
            token_obj = await db_session.scalar(get_token_query)

        return token_obj if token_obj else None

    def use(self):
        self.used = datetime.now(timezone.utc)


class PasswordResetToken(Token):
    __mapper_args__ = {"polymorphic_identity": Token.TokenTypes.PASSWORD_RESET.value}


class AccountActivationToken(Token):
    __mapper_args__ = {
        "polymorphic_identity": Token.TokenTypes.ACCOUNT_ACTIVATION.value
    }
