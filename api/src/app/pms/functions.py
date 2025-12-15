from typing import Literal

from app.models.legacy import PM, User


def filter_by_box(box: Literal["inbox", "outbox"], authed_user: User):
    if box == "inbox":
        return PM.recipient_id == authed_user.id
    else:
        return PM.sender_id == authed_user.id
