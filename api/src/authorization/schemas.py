from typing import Dict
from pydantic import BaseModel, EmailStr


class UserInput(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: Dict


class AuthFailedBody(BaseModel):
    invalid_user = True


class AuthFailed(BaseModel):
    error: AuthFailedBody
