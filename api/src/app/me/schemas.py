import datetime
from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, field_validator

from app.models import User
from app.models.user_meta import PostSide
from app.schema_base import SchemaBase, filtered_str, strip_whitespace

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserOutput(BaseModel):
    id: int
    username: str
    avatar: str
    joinDate: datetime.datetime | None = None
    pronouns: str | None = filtered_str(pipelines=[strip_whitespace])
    birthday: datetime.date | None = None
    showAge: bool | None = None
    location: str | None = filtered_str(pipelines=[strip_whitespace])
    pmMail: bool | None = None
    newGameMail: bool | None = None
    gmMail: bool | None = None
    postSide: PostSide = "r"
    lookingForAGame: bool | None = None
    games: str | None = filtered_str(pipelines=[strip_whitespace])


class UpdateProfileInput(SchemaBase):
    pronouns: str | None = filtered_str(pipelines=[strip_whitespace])
    birthday: datetime.date | None = None
    showAge: bool | None = None
    location: str | None = filtered_str(pipelines=[strip_whitespace])
    pmMail: bool | None = None
    newGameMail: bool | None = None
    gmMail: bool | None = None
    postSide: PostSide = "r"
    lookingForAGame: bool | None = None
    games: str | None = filtered_str(pipelines=[strip_whitespace])

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, v: datetime.date | None) -> datetime.date | None:
        if v and v > datetime.date.today():
            raise ValueError("Birthday cannot be in the future")
        return v


class UpdatedProfileFields(BaseModel):
    pronouns: str | None = None
    birthday: datetime.date | None = None
    showAge: bool | None = None
    location: str | None = None
    pmMail: bool | None = None
    newGameMail: bool | None = None
    gmMail: bool | None = None
    postSide: PostSide | None = None
    lookingForAGame: bool | None = None
    games: str | None = None


class UpdateProfileResponse(BaseModel):
    success: bool = True
    updated: UpdatedProfileFields


class UpdateAvatarResponse(BaseModel):
    success: bool = True
    avatar: str


class DeleteAvatarResponse(BaseModel):
    success: bool = True


class UpdatePasswordInput(BaseModel):
    oldPassword: str
    password: Password
    confirmPassword: Password


class UpdatePasswordResponse(BaseModel):
    success: bool = True


class GetHeaderResponse(BaseModel):
    characters: list = []
    games: list = []
    pmCount: int = 0
