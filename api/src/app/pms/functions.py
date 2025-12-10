from typing import Literal

from app.models.legacy import PMs, User


def filter_by_box(box: Literal["inbox", "outbox"], authed_user: User):
    if box == "inbox":
        return PMs.recipient_id == authed_user.id
    else:
        return PMs.sender_id == authed_user.id
