from fastapi import APIRouter, Body, status
from pydantic import EmailStr
from sqlalchemy import and_, select

from app.auth import schemas
from app.auth.functions import activate_account, send_activation_email
from app.configs import configs
from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.email import get_template, send_email
from app.helpers.functions import error_response
from app.models import PasswordResetToken, User
from app.repositories import UserRepository
from app.schemas import ErrorItem
from app.users import functions as users_functions
from app.users.exceptions import UserExists

auth = APIRouter(prefix="/auth")


@auth.post(
    "/login",
    response_model=schemas.AuthResponse,
)
@public
async def login(user_details: schemas.UserInput, db_session: DBSessionDependency):
    user = await db_session.scalar(
        select(User)
        .where(and_(User.email == user_details.email, User.activated_on.is_not(None)))
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
        errors=[ErrorItem(code="invalid_user", detail="Invalid username or password")],
    )


@auth.post(
    "/register",
    response_model=schemas.RegistrationResponse,
)
@public
async def register(
    user_details: schemas.RegisterInput, db_session: DBSessionDependency
):
    errors: list[ErrorItem] = []
    pass_invalid = User.validate_password(user_details.password)
    if pass_invalid:
        for e in pass_invalid:
            e.field = "password"
        errors = pass_invalid

    if len(errors):
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=errors,
        )

    try:
        new_user = await users_functions.register_user(
            db_session,
            email=user_details.email,
            username=user_details.username,
            password=user_details.password,
        )
        await send_activation_email(new_user)

        return {"registered": True}
    except UserExists as e:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=e.errors,
        )


@auth.post("/resendActivation")
@public
async def resend_activation(
    db_session: DBSessionDependency, email: EmailStr = Body(..., embed=True)
):
    user_repository = UserRepository(db_session)
    user = await user_repository.get_user_by_email(email)
    if user:
        await send_activation_email(user)
    return {"success": True}


@auth.post("/activate/{token}")
@public
async def activate_user(token: str, db_session: DBSessionDependency):
    activated = await activate_account(db_session, token)
    if not activated:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="invalid_token", detail="Invalid token")],
        )
    return {"success": True}


@auth.post("/password_reset")
@public
async def generate_password_reset(
    db_session: DBSessionDependency, email: EmailStr = Body(..., embed=True)
):
    user = await db_session.scalar(select(User).where(User.email == email).limit(1))
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="no_account", detail="No account found")],
        )

    password_reset_token = await db_session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id).limit(1)
    )
    if not password_reset_token:
        password_reset_token = PasswordResetToken(user=user)
        db_session.add(password_reset_token)
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
    reset_details: schemas.ResetPasswordInput, db_session: DBSessionDependency
):
    password_reset = await PasswordResetToken.validate_token(
        token=reset_details.token, email=reset_details.email
    )
    if not password_reset:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="invalid_token", detail="Invalid token")],
        )

    errors: list[ErrorItem] = []
    if reset_details.password != reset_details.confirm_password:
        errors.append(
            ErrorItem(code="password_mismatch", detail="Passwords do not match")
        )
    pass_invalid = User.validate_password(reset_details.password)
    if len(pass_invalid):
        errors.append(ErrorItem(code="invalid_password", detail="Invalid password"))

    if errors:
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, errors=errors)

    user = password_reset.user
    user.set_password(reset_details.password)
    db_session.add(user)
    password_reset.use()
    db_session.add(password_reset)

    return {"success": True}
