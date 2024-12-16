from fastapi import APIRouter, Body, status
from pydantic import UUID4, EmailStr
from sqlalchemy import and_, select

from auth import schemas
from auth.functions import send_activation_email
from database import DBSessionDependency
from envs import HOST_NAME
from helpers.decorators import public
from helpers.email import get_template, send_email
from helpers.functions import error_response
from models import AccountActivationToken, PasswordResetToken, Token, User
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
        select(User)
        .where(and_(User.email == user_details.email, User.activated_on != None))
        .limit(1)
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
        new_user = await users_functions.register_user(
            email=user_details.email,
            username=user_details.username,
            password=user_details.password,
        )
        await send_activation_email(new_user)

        return {"registered": True}
    except UserExists as e:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=e.errors,
        )


@auth.post("/activate/{token}")
@public
async def activate_user(token: str, db_session: DBSessionDependency):
    account_activation_token = await AccountActivationToken.validate_token(token)
    if not account_activation_token:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"invalid_token": True},
        )

    account_activation_token.user.activate()
    db_session.add(account_activation_token.user)
    account_activation_token.use()
    db_session.add(account_activation_token)
    await db_session.commit()

    return {"success": True}


@auth.post("/password_reset")
async def generate_password_reset(
    db_session: DBSessionDependency, email: EmailStr = Body(..., embed=True)
):
    user = await db_session.scalar(select(User).where(User.email == email).limit(1))
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"no_account": True},
        )

    password_reset_token = await db_session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id).limit(1)
    )
    if not password_reset_token:
        password_reset_token = PasswordResetToken(user=user)
        db_session.add(password_reset_token)
        await db_session.commit()
    email_content = get_template(
        "auth/templates/reset_password.html",
        reset_link=f"{HOST_NAME}/activate/{password_reset_token.token}",
    )
    icecream.ic(password_reset_token.token)
    send_email(email, "Password reset for Gamers' Plane", email_content)

    return {"success": True}


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
