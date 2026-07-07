from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import User

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserInput(BaseModel):
    identifier: str
    password: Password

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < User.MIN_PASSWORD_LENGTH:
            raise ValueError("Password must be at least 8 characters long")
        return v


class RegistrationResponse(BaseModel):
    registered: bool = True


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: dict


class RegisterInput(UserInput):
    email: EmailStr
    username: str = Field(..., pattern=r"^[a-zA-Z]+$")
    password: Password


class PasswordResetResponse(BaseModel):
    valid_token: bool


class ResetPasswordInput(BaseModel):
    email: EmailStr
    token: str
    password: Password
    confirm_password: Password
