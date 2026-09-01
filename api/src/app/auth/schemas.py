from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field

from app.models import User
from app.schema_base import SchemaBase


def _validate_password_length(v: str) -> str:
    if len(v) < User.MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {User.MIN_PASSWORD_LENGTH} characters long"
        )
    return v


Password = Annotated[str, AfterValidator(_validate_password_length)]


class UserInput(SchemaBase):
    identifier: str
    password: Password


class RegistrationResponse(SchemaBase):
    registered: bool = True


class AuthResponse(SchemaBase):
    logged_in: bool
    jwt: str
    user: dict


class RegisterInput(SchemaBase):
    email: EmailStr
    username: str = Field(..., pattern=r"^[a-zA-Z]\w+$")
    password: Password


class PasswordResetResponse(SchemaBase):
    valid_token: bool


class RefreshResponse(SchemaBase):
    jwt: str


class ResetPasswordInput(SchemaBase):
    email: EmailStr
    token: str
    password: Password
    confirm_password: Password
