from app.exceptions import ForbiddenException
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Post, User


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
