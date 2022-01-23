from fastapi import APIRouter, status, Body
from pydantic import UUID1, EmailStr

from envs import HOST_NAME
from helpers.functions import error_response
from helpers.email import get_template, send_email
from schemas import ErrorResponse

from authorization import schemas
from users.models import User
from users import functions as users_functions
from users.exceptions import UserExists
from tokens.models import AccountActivationToken, PasswordResetToken


authorization = APIRouter(prefix="/auth")


@authorization.post(
    "/login",
    response_model=schemas.AuthResponse,
    responses={404: {"model": ErrorResponse(error=schemas.AuthFailed())}},
)
def login(user_details: schemas.UserInput):
    email = user_details.email
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        user = None
    if user:
        password = user_details.password
        if user.check_pass(password):
            return {
                "logged_in": True,
                "jwt": user.generate_jwt(),
                "user": user.to_dict(),
            }
    return error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"invalid_user": True},
    )


@authorization.post(
    "/register",
    response_model=schemas.Register,
)
def register(user_details: schemas.Register):
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
        users_functions.register_user(
            email=user_details.email,
            username=user_details.username,
            password=user_details.password,
        )
    except UserExists as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content=e.errors,
        )


@authorization.post("/activate/{token}")
def activate_user(token: UUID1):
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


@authorization.post("/password_reset")
def generate_password_reset(email: EmailStr = Body(..., embed=True)):
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
        "authorization/templates/reset_password.html",
        reset_link=f"{HOST_NAME}/activate/{password_reset.token}",
    )
    send_email(email, "Password reset for Gamers' Plane", email_content)

    return {}


@authorization.get(
    "/password_reset",
    response_model=schemas.PasswordResetResponse,
)
def check_password_reset(email: EmailStr, token: str):
    valid_token = PasswordResetToken.validate_token(token=token, email=email)
    return {"valid_token": valid_token}


@authorization.patch("/password_reset")
def reset_password(reset_details: schemas.ResetPasswordInput):
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
