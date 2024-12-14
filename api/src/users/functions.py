from typing import Union

from sqlalchemy import or_, select

from auth.functions import send_activation_email
from database import session_manager
from models import User, UserMeta
from users.exceptions import UserExists


async def check_for_existing_user(user: User) -> Union[object, None]:
    async with session_manager.session() as db_session:
        get_user = await db_session.execute(
            select(User.email, User.username)
            .where(or_(User.email == user.email, User.username == user.username))
            .limit(2)
        )
        if get_user:
            errors = {}
            for reg_email, reg_username in get_user:
                if reg_email == user.email:
                    errors["email_taken"] = True
                if reg_username == user.username:
                    errors["username_taken"] = True
            if len(errors):
                return errors


async def register_user(email: str, username: str, password: str) -> User:
    new_user = User(email=email, username=username)
    new_user.set_password(password)
    errors = await check_for_existing_user(new_user)
    if errors:
        raise UserExists({"errors": errors})

    async with session_manager.session() as db_session:
        new_user.meta.append(
            UserMeta(key=UserMeta.MetaKeys.NEW_GAME_MAIL.value, value=True)
        )
        new_user.meta.append(UserMeta(key=UserMeta.MetaKeys.POST_SIDE.value, value="l"))
        new_user.meta.append(
            UserMeta(key=UserMeta.MetaKeys.SHOW_AVATARS.value, value=True)
        )

        db_session.add(new_user)
        await db_session.commit()

    return new_user
