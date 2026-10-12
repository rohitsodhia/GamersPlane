from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.exceptions import ForbiddenException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.models import (
    Character,
    CharacterAvatar,
    Forum,
    Post,
    PostRoll,
    QuickNPC,
    User,
)
from app.posts.schemas import PostedAsData, PostedNPCData, RollVisibilityInput
from app.helpers.prose import (
    MAX_ROSTER_TITLE_LENGTH,
    content_npc_ids,
    is_valid_id,
    raw_content_npc_ids,
    roster_attrs,
)
from app.quick_npcs.functions import (
    build_image_data,
    npc_image_url,
    require_npc_image,
)
from app.quick_npcs.schemas import PostedNPCInput, ContentNPCData
from app.repositories import (
    CharacterRepository,
    NPCOwner,
    PlayerRepository,
    QuickNPCRepository,
)


def can_post_as(
    character: Character, forum: Forum, principal: User, is_gm: bool
) -> bool:
    """Whether ``principal`` may post in ``forum`` as ``character``.

    The character must be an approved, named one of the forum's game, and be the
    principal's own, or the principal a GM of the game (``is_gm``). Both the
    options endpoint and the write-path validation go through this.
    """
    return (
        forum.game_id is not None
        and character.game_id == forum.game_id
        and character.approved
        and bool((character.name or "").strip())
        and (character.user_id == principal.id or is_gm)
    )


async def validate_posted_as(
    db_session: AsyncSession, principal: User, forum: Forum, character_id: int
) -> Character:
    """The character to post as, or ``ValidationError`` if ``principal`` can't."""
    if forum.game_id is None:
        raise ValidationError("Characters can only post in game forums")
    character = await CharacterRepository(
        db_session, principal=principal
    ).get_with_avatars(character_id)
    is_gm = (
        character is not None
        and character.user_id != principal.id
        and await PlayerRepository(db_session, principal=principal).is_gm(
            forum.game_id, principal.id
        )
    )
    if character is None or not can_post_as(character, forum, principal, is_gm):
        raise ValidationError("You can't post as that character here")
    return character


def require_one_poster(
    posted_as_id: int | None, posted_npc: PostedNPCInput | None
) -> None:
    """A post is as a character or as a quick NPC, never both."""
    if posted_as_id is not None and posted_npc is not None:
        raise ValidationError("Choose either a character or a quick NPC, not both")


async def resolve_posted_npc(
    db_session: AsyncSession,
    principal: User,
    forum: Forum,
    posted_npc: PostedNPCInput,
) -> QuickNPC:
    """The live NPC for the name + image, made if need be. In a game forum it comes
    from the game's library, and only the game's accepted players may post as one;
    elsewhere it comes from the poster's personal library. The image must be from
    the same library."""
    if forum.game_id is not None:
        if not await PlayerRepository(db_session, principal=principal).is_member(
            forum.game_id, principal.id
        ):
            raise ValidationError("Only the game's players can post as a quick NPC")
        owner = NPCOwner.game(forum.game_id)
    else:
        owner = NPCOwner.user(principal.id)
    npc_repository = QuickNPCRepository(db_session, principal=principal)
    image = (
        await require_npc_image(npc_repository, owner, posted_npc.image_id)
        if posted_npc.image_id is not None
        else None
    )
    return await npc_repository.get_or_create(owner, posted_npc.name, image)


def validate_roster(attrs: dict) -> None:
    """Raise ``ValidationError`` unless a roster block's attrs are well-formed: a
    short (or no) title and a non-empty list of distinct NPC ids. Whether the NPCs
    are usable is checked separately."""
    title = attrs.get("title", "")
    if not isinstance(title, str):
        raise ValidationError("A roster's title must be text")
    if len(title) > MAX_ROSTER_TITLE_LENGTH:
        raise ValidationError(
            f"A roster's title can be at most {MAX_ROSTER_TITLE_LENGTH} characters"
        )
    ids = attrs.get("npcIds")
    if not isinstance(ids, list) or not all(is_valid_id(npc_id) for npc_id in ids):
        raise ValidationError("A roster block needs a valid list of NPCs")
    if not ids:
        raise ValidationError("A roster needs at least one NPC")
    if len(set(ids)) != len(ids):
        raise ValidationError("A roster can't list an NPC twice")


async def validate_content_npcs(
    db_session: AsyncSession,
    principal: User,
    forum: Forum,
    body: dict,
    previous_body: dict | None = None,
) -> None:
    """Raise ``ValidationError`` unless every quick NPC speaker and roster block in
    ``body`` is well-formed and names a live NPC of the right library: the game's
    (and ``principal`` an accepted player) in a game forum, else ``principal``'s
    own. Ids already in
    ``previous_body`` (an edit) aren't re-checked, so an old post stays editable
    after its NPC is deleted or its author leaves the game."""
    for attrs in roster_attrs(body):
        validate_roster(attrs)
    raw_ids = raw_content_npc_ids(body)
    if not all(is_valid_id(npc_id) for npc_id in raw_ids):
        raise ValidationError("A speaker or roster block needs a valid NPC")
    new_ids = set(raw_ids)
    if previous_body is not None:
        new_ids -= set(content_npc_ids(previous_body))
    if not new_ids:
        return

    if forum.game_id is not None:
        if not await PlayerRepository(db_session, principal=principal).is_member(
            forum.game_id, principal.id
        ):
            raise ValidationError("Only the game's players can use a quick NPC")
        owner = NPCOwner.game(forum.game_id)
    else:
        owner = NPCOwner.user(principal.id)
    live = await QuickNPCRepository(db_session, principal=principal).live_ids(
        owner, sorted(new_ids)
    )
    if new_ids - live:
        raise ValidationError("A speaker or roster block's NPC isn't in this library")


async def load_content_npcs(
    db_session: AsyncSession, principal: User | None, bodies: list[dict]
) -> dict[int, ContentNPCData]:
    """Every NPC the speaker and roster blocks of ``bodies`` name, by id, in one query. Deleted
    NPCs are included."""
    ids = list(dict.fromkeys(i for body in bodies for i in content_npc_ids(body)))
    npcs = await QuickNPCRepository(db_session, principal=principal).get_many(ids)
    return {
        npc.id: ContentNPCData(
            id=npc.id,
            name=npc.name,
            image=build_image_data(npc.image) if npc.image is not None else None,
        )
        for npc in npcs
    }


def build_content_npcs(
    body: dict, loaded: dict[int, ContentNPCData]
) -> list[ContentNPCData]:
    """The NPCs ``body``'s speaker and roster blocks name, from ``load_content_npcs``' result."""
    return [loaded[i] for i in content_npc_ids(body) if i in loaded]


def is_same_npc(npc: QuickNPC | None, posted_npc: PostedNPCInput | None) -> bool:
    """Whether ``posted_npc`` (as sent) is the NPC a post already has."""
    if npc is None or posted_npc is None:
        return npc is None and posted_npc is None
    return npc.name == posted_npc.name and npc.image_id == posted_npc.image_id


def build_posted_npc(post: Post) -> PostedNPCData | None:
    """The quick NPC ``post`` was made as, even if it has since been deleted."""
    npc = post.posted_npc
    if npc is None:
        return None
    return PostedNPCData(
        id=npc.id,
        name=npc.name,
        image=npc_image_url(npc.image) if npc.image is not None else None,
    )


def validate_posted_avatar(character: Character | None, avatar_id: int | None) -> None:
    """Raise ``ValidationError`` if ``avatar_id`` isn't one of ``character``'s
    avatars (``character`` is the post's resulting one, ``None`` for as the
    author). ``None`` always passes, meaning the primary avatar."""
    if avatar_id is None:
        return
    if character is None:
        raise ValidationError(
            "An avatar can only be chosen when posting as a character"
        )
    if not any(avatar.id == avatar_id for avatar in character.avatars):
        raise ValidationError("That avatar isn't one of the character's")


def avatar_url(avatar: CharacterAvatar) -> str:
    return f"{configs.AVATARS_ROOT}/characters/{avatar.id}.{avatar.ext}"


def posted_avatar(
    character: Character, avatar_id: int | None = None
) -> CharacterAvatar | None:
    """The avatar to show for ``character``: ``avatar_id`` if it's still one of
    theirs, else the primary (``None`` if they have no primary)."""
    chosen = next(
        (avatar for avatar in character.avatars if avatar.id == avatar_id), None
    )
    if chosen is None:
        chosen = next((a for a in character.avatars if a.is_primary), None)
    return chosen


def posted_avatar_url(character: Character, avatar_id: int | None = None) -> str | None:
    """The URL of ``posted_avatar``, if there is one."""
    chosen = posted_avatar(character, avatar_id)
    return avatar_url(chosen) if chosen is not None else None


def displayable_posted_as(post: Post) -> Character | None:
    """The character ``post`` was made as, unless it's gone or has no name (then
    the post just shows as its author's)."""
    character = post.posted_as
    if character is None or character.deleted is not None:
        return None
    if not (character.name or "").strip():
        return None
    return character


async def viewer_gm_game_id(
    db_session: AsyncSession, viewer: User | None, forum: Forum, posts: list[Post]
) -> int | None:
    """The forum's game if ``viewer`` is its GM, for ``build_posted_as``. Skips
    the lookup when no post is made as a character."""
    if (
        viewer is None
        or forum.game_id is None
        or not any(post.posted_as is not None for post in posts)
    ):
        return None
    is_gm = await PlayerRepository(db_session, principal=viewer).is_gm(
        forum.game_id, viewer.id
    )
    return forum.game_id if is_gm else None


def build_posted_as(
    post: Post, viewer: User | None, gm_game_id: int | None
) -> PostedAsData | None:
    """``post``'s character as ``viewer`` sees it. ``gm_game_id`` is the game
    the viewer is a GM of, if any, so it's looked up once for many posts."""
    character = displayable_posted_as(post)
    if character is None:
        return None
    can_view = character.in_library or (
        viewer is not None
        and (
            character.user_id == viewer.id
            or (gm_game_id is not None and character.game_id == gm_game_id)
        )
    )
    avatar = posted_avatar(character, post.posted_avatar_id)
    return PostedAsData(
        id=character.id,
        name=(character.name or "").strip(),
        avatar_id=avatar.id if avatar is not None else None,
        avatar=avatar_url(avatar) if avatar is not None else None,
        can_view=can_view,
    )


def validate_roll_visibility(
    rolls: list[PostRoll], changes: list[RollVisibilityInput]
) -> list[tuple[PostRoll, RollVisibilityInput]]:
    """Pair each requested visibility change with the post's roll it targets.

    Raises ``ValidationError`` if an id isn't one of ``rolls`` (the post's own
    rolls) or is listed twice.
    """
    by_id = {roll.id: roll for roll in rolls}
    if len({change.id for change in changes}) != len(changes):
        raise ValidationError("A roll can only be listed once")
    pairs = []
    for change in changes:
        if change.id not in by_id:
            raise ValidationError(f"Roll {change.id} isn't on this post")
        pairs.append((by_id[change.id], change))
    return pairs


def check_post_change(
    permissions: ForumPermissions, post: Post, principal: User, verb: Verbs
) -> None:
    """Raise unless the principal may edit/delete ``post`` (``verb`` says which).

    Moderators may change any post, locked thread or not. Everyone else may only
    change their own posts, in an unlocked thread, with ``verb`` on the forum.
    """
    forum = post.thread.forum
    if permissions.has(forum, Verbs.FORUM_MODERATE):
        return
    if post.author_id != principal.id:
        raise ForbiddenException("You are not the author of this post")
    if post.thread.options.locked:
        raise ForbiddenException("Thread is locked")
    if not permissions.has(forum, verb):
        raise ForbiddenException("You don't have permission to do that here")
