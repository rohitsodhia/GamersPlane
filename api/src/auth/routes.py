from fastapi import APIRouter, Body, status
from pydantic import UUID1, EmailStr
from sqlalchemy import select

from auth import schemas
from database import DBSessionDependency
from envs import HOST_NAME
from helpers.decorators import public
from helpers.email import get_template, send_email
from helpers.functions import error_response
from models import AccountActivationToken, PasswordResetToken, User
from schemas import ErrorResponse
from users import functions as users_functions
from users.exceptions import UserExists

auth = APIRouter(prefix="/auth")


@auth.post(
    "/login",
    response_model=schemas.AuthResponse,
    responses={404: {"model": ErrorResponse(error=schemas.AuthFailed())}},
)
@public
async def login(user_details: schemas.UserInput, db_session: DBSessionDependency):
    email = user_details.email
    user = await db_session.scalar(
        select(User).where(User.email == user_details.email).limit(1)
    )
    if user:
        password = user_details.password
        if user.check_pass(password):
            return {
                "logged_in": True,
                "jwt": user.generate_jwt(),
                "user": {
                    "username": user.username,
                    "email": user.email,
                },
            }
    return error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"invalid_user": True},
    )


@auth.post(
    "/register",
    response_model=schemas.RegistrationResponse,
)
@public
async def register(user_details: schemas.Register):
    errors = {}
    pass_invalid = User.validate_password(user_details.password)
    if pass_invalid:
        errors["pass_errors"] = pass_invalid

    if len(errors):
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content=errors,
        )

    try:
        await users_functions.register_user(
            email=user_details.email,
            username=user_details.username,
            password=user_details.password,
        )
        return {"registered": True}
    except UserExists as e:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=e.errors,
        )


@auth.post("/activate/{token}")
async def activate_user(token: UUID1):
    try:
        account_activation_token = AccountActivationToken.objects.get(token=token)
    except AccountActivationToken.DoesNotExist:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"invalid_token": True},
        )

    user = account_activation_token.user
    user.activate()
    account_activation_token.use()
    return {}


@auth.post("/password_reset")
async def generate_password_reset(email: EmailStr = Body(..., embed=True)):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"no_account": True},
        )

    try:
        password_reset = PasswordResetToken.objects.get(user=user)
    except PasswordResetToken.DoesNotExist:
        password_reset = PasswordResetToken(user=user)
        password_reset.save()
    email_content = get_template(
        "auth/templates/reset_password.html",
        reset_link=f"{HOST_NAME}/activate/{password_reset.token}",
    )
    send_email(email, "Password reset for Gamers' Plane", email_content)

    return {}


@auth.get(
    "/password_reset",
    response_model=schemas.PasswordResetResponse,
)
async def check_password_reset(email: EmailStr, token: str):
    valid_token = PasswordResetToken.validate_token(token=token, email=email)
    return {"valid_token": valid_token}


@auth.patch("/password_reset")
async def reset_password(reset_details: schemas.ResetPasswordInput):
    password_reset = PasswordResetToken.validate_token(
        token=reset_details.token, email=reset_details.email, get_obj=True
    )
    if not password_reset:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND, content={"invalid_token": True}
        )

    errors = {}
    if reset_details.password != reset_details.confirm_password:
        errors["password_mismatch"] = True
    pass_invalid = User.validate_password(reset_details.password)
    if len(pass_invalid):
        errors["pass_errors"] = pass_invalid

    if errors:
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, content=errors)

    user = password_reset.user
    user.set_password(reset_details.password)
    user.save()
    password_reset.use()

    return {}
