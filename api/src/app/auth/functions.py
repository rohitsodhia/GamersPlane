from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.configs import configs
from app.helpers.email import get_template, send_email
from app.models import AccountActivationToken, PasswordResetToken, Token, User
from app.schemas import ErrorItem


def validate_password_change(password: str, confirm_password: str) -> list[ErrorItem]:
    errors: list[ErrorItem] = []
    if password != confirm_password:
        errors.append(
            ErrorItem(code="password_mismatch", detail="Passwords do not match")
        )
    if User.validate_password(password):
        errors.append(ErrorItem(code="invalid_password", detail="Invalid password"))
    return errors


async def get_usable_reset_token(
    db_session: AsyncSession, token: str
) -> PasswordResetToken | None:
    """The password-reset token for ``token`` if it exists and is still usable
    (unused and within its TTL). Unknown, malformed, used, expired, and
    other-type tokens all come back as ``None``."""
    found = await Token.validate_token(db_session, token=token)
    if isinstance(found, PasswordResetToken) and found.is_usable:
        return found
    return None


async def send_password_reset_email(db_session: AsyncSession, user: User) -> None:
    """Retire the user's outstanding reset tokens, mint a fresh one, and email
    the link."""
    await db_session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_(None))
        .values(used=func.now())
    )
    reset_token = PasswordResetToken(user=user)
    db_session.add(reset_token)
    # Flush so the column-default token is populated before building the link
    await db_session.flush()
    email_content = get_template(
        "auth/templates/reset_password.html",
        reset_link=f"{configs.HOST_NAME}/reset-password?token={reset_token.token}",
    )
    await send_email(user.email, "Password reset for Gamers' Plane", email_content)


async def get_activation_link(db_session: AsyncSession, user: User) -> str:
    account_activation_token = await db_session.scalar(
        select(AccountActivationToken)
        .where(AccountActivationToken.user_id == user.id)
        .limit(1)
    )
    if not account_activation_token:
        account_activation_token = AccountActivationToken(user_id=user.id)
        db_session.add(account_activation_token)
        await db_session.flush()

    return f"{configs.HOST_NAME}/activate?token={account_activation_token.token}"


async def activate_account(db_session: AsyncSession, token: str) -> bool:
    account_activation_token = await db_session.scalar(
        select(AccountActivationToken)
        .options(joinedload(AccountActivationToken.user))
        .where(AccountActivationToken.token == token)
        .limit(1)
    )
    if not account_activation_token:
        return False

    account_activation_token.user.activate()
    account_activation_token.use()
    return True


async def send_activation_email(db_session: AsyncSession, user: User) -> None:
    email_content = get_template(
        "auth/templates/activation.html",
        activation_link=await get_activation_link(db_session, user),
    )
    await send_email(user.email, "Activate your Gamers' Plane account!", email_content)
