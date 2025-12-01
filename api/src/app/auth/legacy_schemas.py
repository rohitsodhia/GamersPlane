from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, EmailStr, Field

from app.models.legacy import User

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserInput(BaseModel):
    user: str
    password: Password


class RegistrationResponse(BaseModel):
    registered: bool = True


class AuthResponse(BaseModel):
    success: bool


class AuthFailed(BaseModel):
    invalid_user: bool = True


class Register(UserInput):
    username: str = Field(..., pattern=r"^[a-zA-Z]+$")


class PasswordResetResponse(BaseModel):
    valid_token: bool


class ResetPasswordInput(BaseModel):
    email: EmailStr
    token: str
    password: Password
    confirm_password: Password
