from sqlalchemy import select

from database import session_manager
from envs import HOST_NAME
from helpers.email import get_template, send_email
from models import AccountActivationToken, User


async def get_activation_link(user: User) -> str:
    async with session_manager.session() as db_session:
        account_activation_token = await db_session.scalar(
            select(AccountActivationToken)
            .where(AccountActivationToken.user_id == user.id)
            .limit(1)
        )
        if not account_activation_token:
            account_activation_token = AccountActivationToken(user=user)
            db_session.add(account_activation_token)
            await db_session.commit()

    return f"{HOST_NAME}/activate/{account_activation_token.token}"


async def send_activation_email(user: User) -> None:
    email_content = get_template(
        "auth/templates/activation.html",
        activation_link=await get_activation_link(user),
    )
    send_email(user.email, "Activate your Gamers' Plane account!", email_content)
