from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.exceptions import ForbiddenException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Character, Forum, Post, PostRoll, User
from app.posts.schemas import PostedAsData, RollVisibilityInput
from app.repositories import CharacterRepository, PlayerRepository


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


def primary_avatar_url(character: Character) -> str | None:
    avatar = next((avatar for avatar in character.avatars if avatar.is_primary), None)
    if avatar is None:
        return None
    return f"{configs.AVATARS_ROOT}/characters/{avatar.id}.{avatar.ext}"


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
    return PostedAsData(
        id=character.id,
        name=(character.name or "").strip(),
        avatar=primary_avatar_url(character),
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
