from typing import Dict

from pydantic import BaseModel, EmailStr, Field

from fields import Password


class UserInput(BaseModel):
    email: EmailStr
    password: Password


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: Dict


class AuthFailed(BaseModel):
    invalid_user = True


class Register(UserInput):
    username: str = Field(..., regex="^[a-zA-Z]")


class PasswordResetResponse(BaseModel):
    valid_token: str


class ResetPasswordInput(BaseModel):
    email: EmailStr
    token: str
    password: Password
    confirm_password: Password
