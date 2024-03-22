from typing import Dict, Optional
from pydantic import BaseModel, EmailStr, Field


class ContactInput(BaseModel):
    name: str
    username: Optional[str] = None
    email: EmailStr
    subject: str
    message: str


class AuthResponse(BaseModel):
    logged_in: bool
    jwt: str
    user: Dict


class AuthFailed(BaseModel):
    invalid_user = True
