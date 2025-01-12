from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, EmailStr, Field, field_validator

from models import User

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserInput(BaseModel):
    email: EmailStr
    password: Password

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class RegistrationResponse(BaseModel):
    registered: bool = True


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: dict


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
