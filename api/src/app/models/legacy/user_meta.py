from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.exceptions import ValidationError
from app.helpers.enums import LabelEnum
from app.models.legacy.base import LegacyBase


class UserMeta(LegacyBase):
    class MetaKeys(LabelEnum):
        AVATAR_EXT = "avatarExt", "Avatar Extension", bool
        LOCATION = "location", "Location", str
        NEW_GAME_MAIL = "newGameMail", "New Game Mail", bool
        POST_SIDE = "postSide", "Post Side", str
        REFERENCE = "reference", "Reference", str
        SHOW_AVATARS = "showAvatars", "Show Avatars", bool
        SHOW_TZ = "showTZ", "Show Timezone", bool
        TIMEZONE = "timezone", "Timezone", str

    __tablename__ = "usermeta"

    id: Mapped[int] = mapped_column("metaID", primary_key=True)
    user_id: Mapped[int] = mapped_column("userID", ForeignKey("users.userID"))
    key: Mapped[MetaKeys] = mapped_column("metaKey", String(32))
    _value: Mapped[str] = mapped_column("metaValue", String())
    autoload = mapped_column(Boolean(), default=False)

    @property
    def value(self):
        if self.key not in [e.value for e in self.MetaKeys]:
            return None

        cast_type: type[int | bool | str] = self.MetaKeys(self.key).full_value[2]
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
            if value not in ["l", "r"]:
                raise ValidationError("Post Side must either be 'l' or 'r'")
        elif cast_type is bool:
            value = 1 if value else 0

        self._value = str(value)
