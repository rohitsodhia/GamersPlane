from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, ConfigDict

from app.models.legacy import User

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    read: bool


class PM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient: UserDetails
    sender: UserDetails
    title: str
    message: str
    reply_to_id: int | None


class PMsListResponse(BaseModel):
    pms: list[PM]
    count: int
    page: int


class NewPM(BaseModel):
    username: str
    reply_to_id: int | None = None
    title: str
    message: str


class NewPMResponse(BaseModel):
    sent: bool = True


class NoRecipientResponse(BaseModel):
    noRecipient: bool = True


class PMSelfResponse(BaseModel):
    messagingSelf: bool = True
