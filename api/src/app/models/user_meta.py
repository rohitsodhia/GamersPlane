from typing import Literal, get_args

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.exceptions import ValidationError
from app.helpers.enums import LabelEnum
from app.models.base import Base

PostSide = Literal["r", "l", "c"]


class UserMeta(Base):
    class MetaKeys(LabelEnum):
        AVATAR_EXT = "avatarExt", "Avatar Extension", str
        BIRTHDAY = "birthday", "Birthday", str
        GAMES = "games", "Games", str
        GM_MAIL = "gmMail", "GM Mail", bool
        LOCATION = "location", "Location", str
        LOOKING_FOR_A_GAME = "lookingForAGame", "Looking For A Game", bool
        NEW_GAME_MAIL = "newGameMail", "New Game Mail", bool
        PM_MAIL = "pmMail", "PM Mail", bool
        POST_SIDE = "postSide", "Post Side", str
        PRONOUNS = "pronouns", "Pronouns", str
        REFERENCE = "reference", "Reference", str
        SHOW_AGE = "showAge", "Show Age", bool
        SHOW_AVATARS = "showAvatars", "Show Avatars", bool
        SHOW_TZ = "showTZ", "Show Timezone", bool
        TIMEZONE = "timezone", "Timezone", str

    __tablename__ = "user_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[MetaKeys] = mapped_column(String(32))
    _value: Mapped[str] = mapped_column("value", String())

    @property
    def value(self):
        if self.key not in [e.value for e in self.MetaKeys]:
            return None

        cast_type: type[int | bool | str] = self.MetaKeys(self.key).full_value[2]
        if cast_type is bool:
            return self._value == "1"
        return cast_type(self._value)

    @value.setter
    def value(self, value):
        if self.key not in [e.value for e in self.MetaKeys]:
            raise ValueError("No key set")

        cast_type: type[int | bool | str] = self.MetaKeys(self.key).full_value[2]
        if type(value) is not cast_type:
            raise ValidationError(f"{self.key} must be a {str(cast_type)[8:-2]}")
        if self.key == self.MetaKeys.POST_SIDE.value:
            value = value.lower()
            if value not in get_args(PostSide):
                raise ValidationError("Post Side must either be 'r', 'l', or 'c'")
        elif cast_type is bool:
            value = 1 if value else 0

        self._value = str(value)
