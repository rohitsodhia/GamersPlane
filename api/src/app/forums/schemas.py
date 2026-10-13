from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.quick_npcs.schemas import NPCData
from app.models import Character
from app.models.forum import Forum
from app.schema_base import SchemaBase

ForumTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)
]
ForumDescription = Annotated[str, StringConstraints(strip_whitespace=True)]


class HeritageForumData(SchemaBase):
    id: int
    title: str
    # Whether the principal moderates this ancestor (so can open its ACP).
    moderate: bool


class AuthorData(SchemaBase):
    id: int
    username: str


class LastPostDetails(SchemaBase):
    id: int
    title: str
    datestamp: str
    author: AuthorData


class ChildForumData(SchemaBase):
    id: int
    title: str
    description: str | None
    forum_type: Forum.ForumTypes
    parent_id: int | None
    order: int
    thread_count: int
    post_count: int
    # Whether the forum, or a readable subforum, holds a thread the principal
    # hasn't read. Always false for guests.
    has_unread: bool = False
    last_post: LastPostDetails | None
    children: list[ChildForumData] = []


ChildForumData.model_rebuild()


class ModeratedForumData(SchemaBase):
    id: int
    title: str
    # False for a forum listed only as a heading over forums the principal
    # moderates.
    moderate: bool
    children: list[ModeratedForumData] = []


ModeratedForumData.model_rebuild()


class GetForumBreadcrumbsResponse(SchemaBase):
    id: int
    title: str
    game_id: int | None
    heritage: list[HeritageForumData]


class GetForum(SchemaBase):
    id: int
    title: str
    description: str | None
    forum_type: Forum.ForumTypes
    parent_id: int | None
    heritage: list[HeritageForumData]
    order: int
    game_id: int | None
    thread_count: int
    # As on ChildForumData, for this forum itself (false unless it's readable).
    has_unread: bool = False
    # Forum verbs the principal holds here. A forum shown only because it has
    # readable subforums lacks forum_read, and has no threads to list.
    permissions: list[str]
    children: list[ChildForumData] = []


class UpdateForumInput(SchemaBase):
    # Omitted fields are left alone; an empty description clears it.
    title: ForumTitle | None = None
    description: ForumDescription | None = None


class CreateSubforumInput(SchemaBase):
    title: ForumTitle
    description: ForumDescription | None = None
    forum_type: Forum.ForumTypes = Forum.ForumTypes.FORUM


class DrawableDeck(SchemaBase):
    id: int
    label: str
    type: str
    remaining: int


class GetForumDecksResponse(SchemaBase):
    decks: list[DrawableDeck]


class PostAsOwner(SchemaBase):
    id: int
    username: str


class PostAsAvatar(SchemaBase):
    id: int
    url: str
    is_primary: bool


class PostAsCharacter(SchemaBase):
    id: int
    name: str
    type: Character.Type
    owner: PostAsOwner
    # Primary first, then by id.
    avatars: list[PostAsAvatar] = []
    # When the principal last posted as this character in the game's forums.
    last_used_at: datetime | None = None


class GetForumCharactersResponse(SchemaBase):
    characters: list[PostAsCharacter]
    # The character the principal last posted as in the requested thread, when
    # they can still post as it.
    default_id: int | None = None
    # The avatar of that same post, when it's still one of the character's.
    default_avatar_id: int | None = None
    # The quick NPCs to post as (most recently used first): the game's for its
    # accepted players, else the principal's own.
    npcs: list[NPCData] = []
    # The quick NPC the principal last posted as in the requested thread, when
    # they can still post as it.
    default_npc_id: int | None = None
    # The forum's game, if it has one.
    game_id: int | None = None
    # Whether the principal can make quick NPCs here: an accepted player of the
    # game, which isn't retired; always, outside game forums.
    can_manage_npcs: bool = False


class ForumIdResponse(SchemaBase):
    id: int


class ReorderSubforumsInput(SchemaBase):
    forum_ids: list[int]
