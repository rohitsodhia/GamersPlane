from typing import Annotated

from annotated_types import Len
from pydantic import ConfigDict

from app.helpers.bbcode import BBCode2Html
from app.models.legacy import User
from app.schema_base import SchemaBase, filtered_str

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserDetails(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    read: bool


class PM(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient: UserDetails
    sender: UserDetails
    title: str = filtered_str(add_pipelines=[BBCode2Html])
    message: str = filtered_str(add_pipelines=[BBCode2Html])
    datestamp: str
    reply_to_id: int | None


class PMsListResponse(SchemaBase):
    pms: list[PM]
    count: int
    page: int


class PMWithHistory(PM):
    history: list[PM] = list()


class GetPMResponse(SchemaBase):
    pm: PMWithHistory


class NewPM(SchemaBase):
    username: str
    reply_to_id: int | None = None
    title: str
    message: str


class NewPMResponse(SchemaBase):
    sent: bool = True


class NoRecipientResponse(SchemaBase):
    noRecipient: bool = True


class PMSelfResponse(SchemaBase):
    messagingSelf: bool = True
