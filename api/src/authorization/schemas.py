from typing import Dict
from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    error: BaseModel


class UserInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=7)


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: Dict


class AuthFailed(BaseModel):
    invalid_user = True


class Register(UserInput):
    username: str = Field(..., regex="^[a-zA-Z]")
