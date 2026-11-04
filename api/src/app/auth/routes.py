from fastapi import APIRouter, Body, status
from fastapi.responses import JSONResponse
from pydantic import EmailStr

from app.auth import schemas
from app.auth.functions import (
    activate_account,
    get_usable_reset_token,
    send_activation_email,
    send_password_reset_email,
    validate_password_change,
)
from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response
from app.middleware import Principal, enforce_login_eligibility
from app.models import User
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
    user_repository = UserRepository(db_session)

    identifier = user_details.identifier.lower()
    user = await user_repository.get_user_by_identifier(identifier)
    if user and user.check_pass(user_details.password):
        # Only disclose a ban/suspension once the password checks out, so it
        # isn't a probe for which accounts exist. Raises BannedException /
        # SuspendedException, handled as a 403 with a "banned"/"suspended" code.
        enforce_login_eligibility(user)
        if user.activated_on is None:
            # Safe to include the email: the password already checked out. The
            # frontend uses it to offer POST /auth/resendActivation.
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "errors": [
                        ErrorItem(
                            code="not_activated",
                            detail="This account hasn't been activated yet",
                        ).model_dump(exclude_none=True)
                    ],
                    "email": user.email,
                },
            )
        await user_repository.update_last_activity(user)
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
    "/refresh",
    response_model=schemas.RefreshResponse,
)
async def refresh(current_user: Principal):
    # check_authorization already rejects banned/suspended users on this
    # (non-public) route before the handler runs.
    return {"jwt": current_user.generate_jwt()}


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
        await send_activation_email(db_session, new_user)

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
        await send_activation_email(db_session, user)
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
    # Always the same response, so this can't be used to probe which emails have
    # accounts. Unknown and unactivated emails silently get nothing.
    user = await UserRepository(db_session).get_user_by_email(email)
    if user and user.activated_on is not None:
        await send_password_reset_email(db_session, user)

    return {"success": True}


@auth.get(
    "/password_reset",
    response_model=schemas.PasswordResetResponse,
)
@public
async def check_password_reset(token: str, db_session: DBSessionDependency):
    return {"valid_token": bool(await get_usable_reset_token(db_session, token=token))}


@auth.patch("/password_reset")
@public
async def reset_password(
    reset_details: schemas.ResetPasswordInput, db_session: DBSessionDependency
):
    password_reset = await get_usable_reset_token(db_session, token=reset_details.token)
    if not password_reset:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="invalid_token", detail="Invalid token")],
        )

    errors = validate_password_change(
        reset_details.password, reset_details.confirm_password
    )

    if errors:
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, errors=errors)

    user = password_reset.user
    user.set_password(reset_details.password)
    db_session.add(user)
    password_reset.use()
    db_session.add(password_reset)

    return {"success": True}
