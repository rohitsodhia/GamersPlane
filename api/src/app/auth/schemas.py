from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.models import User


def _validate_password_length(v: str) -> str:
    if len(v) < User.MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {User.MIN_PASSWORD_LENGTH} characters long"
        )
    return v


Password = Annotated[str, AfterValidator(_validate_password_length)]


class UserInput(BaseModel):
    identifier: str
    password: Password


class RegistrationResponse(BaseModel):
    registered: bool = True


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: dict


class RegisterInput(BaseModel):
    email: EmailStr
    username: str = Field(..., pattern=r"^[a-zA-Z]\w+$")
    password: Password


class PasswordResetResponse(BaseModel):
    valid_token: bool


class RefreshResponse(BaseModel):
    jwt: str


class ResetPasswordInput(BaseModel):
    email: EmailStr
    token: str
    password: Password
    confirm_password: Password
