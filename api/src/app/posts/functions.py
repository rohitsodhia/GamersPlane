from app.exceptions import ForbiddenException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Post, PostRoll, User
from app.posts.schemas import RollVisibilityInput


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
