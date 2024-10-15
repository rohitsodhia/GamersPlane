from enum import Enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from exceptions import ValidationError
from models.base import Base


class UserMeta(Base):
    class MetaKeys(Enum):
        AVATAR_EXT = "avatarExt", "Avatar Extension"
        LOCATION = "location", "Location"
        NEW_GAME_MAIL = "newGameMail", "New Game Mail"
        POST_SIDE = "postSide", "Post Side"
        REFERENCE = "reference", "Reference"
        SHOW_AVATARS = "showAvatars", "Show Avatars"
        SHOW_TZ = "showTZ", "Show Timezone"
        TIMEZONE = "timezone", "Timezone"

    __tablename__ = "user_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[MetaKeys] = mapped_column(String(32))
    value: Mapped[str]

    def validate(self):
        match self.key:
            case self.MetaKeys.POST_SIDE:
                if self.value.lower() not in ["l", "r"]:
                    raise ValidationError("Post Side must either be 'l' or 'r'")
                self.value = self.value.lower()
            case (
                self.MetaKeys.NEW_GAME_MAIL
                | self.MetaKeys.SHOW_AVATARS
                | self.MetaKeys.SHOW_TZ
            ):
                if type(self.value) is not bool:
                    raise ValidationError(f"{self.key} must be a boolean")
