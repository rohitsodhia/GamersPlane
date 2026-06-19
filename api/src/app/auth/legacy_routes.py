from fastapi import APIRouter, Body, Request, Response, status
from pydantic import EmailStr
from sqlalchemy import and_, or_, select

from app.auth import legacy_schemas, schemas
from app.auth.functions import send_activation_email
from app.configs import configs
from app.database import LegacyDBSessionDependency
from app.helpers.decorators import public
from app.helpers.email import get_template, send_email
from app.helpers.functions import error_response
from app.models import AccountActivationToken, PasswordResetToken
from app.models.legacy import User
from app.schemas import ErrorResponse
from app.users import functions as users_functions
from app.users.exceptions import UserExists

auth = APIRouter(prefix="/legacy/auth")


@auth.post(
    "/login",
    response_model=legacy_schemas.AuthResponse,
    responses={404: {"model": ErrorResponse[schemas.AuthFailed]}},
)
@public
async def login(
    response: Response,
    db_session: LegacyDBSessionDependency,
    user_details: legacy_schemas.UserInput,
):
    user: User | None = await db_session.scalar(
        select(User)
        .where(
            and_(
                or_(
                    User.username == user_details.user,
                    User.email == user_details.user,
                ),
                User.activated_on.is_not(None),
            )
        )
        .limit(1)
    )
    if user:
        password = user_details.password
        if user.check_pass(password):
            user.set_cookies(response)
            return {"success": True}
    return error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"invalid_user": True},
    )


@auth.post("/logout")
async def logout(request: Request, response: Response):
    secure: bool = configs.ENVIRONMENT != "dev"
    for cookie_name in request.cookies.keys():
        response.delete_cookie(
            key=cookie_name,
            domain=configs.COOKIE_DOMAIN,
            secure=secure,
            httponly=True,
        )
    return {"success": True}


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
async def activate_user(token: str, db_session: LegacyDBSessionDependency):
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
@public
async def generate_password_reset(
    db_session: LegacyDBSessionDependency, email: EmailStr = Body(..., embed=True)
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
        reset_link=f"{configs.HOST_NAME}/activate/{password_reset_token.token}",
    )
    send_email(email, "Password reset for Gamers' Plane", email_content)

    return {"success": True}


@auth.get(
    "/password_reset",
    response_model=schemas.PasswordResetResponse,
)
@public
async def check_password_reset(email: EmailStr, token: str):
    valid_token = await PasswordResetToken.validate_token(token=token, email=email)
    return {"valid_token": bool(valid_token)}


@auth.patch("/password_reset")
@public
async def reset_password(
    reset_details: schemas.ResetPasswordInput, db_session: LegacyDBSessionDependency
):
    password_reset = await PasswordResetToken.validate_token(
        token=reset_details.token, email=reset_details.email
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
    db_session.add(user)
    password_reset.use()
    db_session.add(password_reset)
    await db_session.commit()

    return {"success": True}
