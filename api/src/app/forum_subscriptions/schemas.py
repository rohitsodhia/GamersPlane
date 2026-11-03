from app.schema_base import SchemaBase


class SubscribedForum(SchemaBase):
    id: int
    title: str
    # Null for a top-level forum (the site root is never listed).
    parent_id: int | None
    # False for an ancestor listed only so the tree can be built.
    subscribed: bool


class SubscribedThread(SchemaBase):
    id: int
    title: str


class SubscribedThreadGroup(SchemaBase):
    forum_id: int
    forum_title: str
    threads: list[SubscribedThread]


class GetSubscriptionsResponse(SchemaBase):
    # Flat, for the frontend to nest by parent_id: the subscribed forums the user
    # can read plus all their ancestors.
    forums: list[SubscribedForum]
    thread_groups: list[SubscribedThreadGroup]
