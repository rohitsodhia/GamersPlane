from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union
from uuid import uuid1 as uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


def generate_token() -> str:
    return str(uuid())


class Token(Base, TimestampMixin):
    class TokenTypes(Enum):
        ACCOUNT_ACTIVATION = "aa", "Account Activation"
        PASSWORD_RESET = "pr", "Password Reset"

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_type: Mapped[TokenTypes] = mapped_column(String(2))
    token: Mapped[str] = mapped_column(String(36), default_factory=generate_token)
    requestedOn: Mapped[datetime] = mapped_column(insert_default=func.now())
    used: Mapped[Optional[datetime]]

    __mapper_args__ = {
        "polymorphic_on": "token_type",
        "polymorphic_abstract": True,
    }

    def save(self, *args, **kwargs):
        if self.model_token_type:
            self.token_type = self.model_token_type
        super().save(*args, **kwargs)

    @staticmethod
    def validate_token(
        token: str, email: str = None, get_obj: bool = False
    ) -> Union[bool, object]:
        token = Token.objects.filter(token=token)
        if email:
            token = token.filter(user__email=email)

        if get_obj:
            return token[0] if token else None
        return True if token else False

    def use(self):
        self.used = datetime.now(timezone.utc)
        self.save()
        return self


class PasswordResetToken(Token):
    __mapper_args__ = {"polymorphic_identity": Token.TokenTypes.PASSWORD_RESET.value}


class AccountActivationToken(Token):
    __mapper_args__ = {
        "polymorphic_identity": Token.TokenTypes.ACCOUNT_ACTIVATION.value
    }
