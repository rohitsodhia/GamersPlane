from app.exceptions import ForbiddenException
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Forum, Post, Thread
from app.threads import schemas
from app.threads.option_schemas import ThreadOptionsUpdate

# The forum verb needed to change each thread option. The options themselves
# act as thread-wide switches for everyone posting in the thread.
OPTION_VERBS = {
    "sticky": Verbs.FORUM_MODERATE,
    "locked": Verbs.FORUM_MODERATE,
    "allow_public_posting": Verbs.FORUM_MODERATE,
    "discord_webhook": Verbs.FORUM_MODERATE,
    "allow_rolls": Verbs.FORUM_ADD_ROLLS,
    "allow_draws": Verbs.FORUM_ADD_DRAWS,
}


def build_post_data(post: Post) -> schemas.PostData:
    return schemas.PostData(
        id=post.id,
        title=post.title,
        datestamp=str(post.published_at),
        author=schemas.AuthorData(id=post.author.id, username=post.author.username),
    )


def merge_thread_options(
    permissions: ForumPermissions,
    forum: Forum,
    current: Thread.Options,
    update: ThreadOptionsUpdate,
) -> Thread.Options:
    """Apply a partial update to a thread's options, returning a new object.

    A field changes only if it was sent and differs from the current value, and
    changing it (on or off) needs its ``OPTION_VERBS`` verb. A boolean sent as
    ``null`` is skipped as not sent; ``discord_webhook`` ``null`` clears it.
    """
    changes = {}
    for field in update.model_fields_set:
        value = getattr(update, field)
        if value is None and field != "discord_webhook":
            continue
        if value == getattr(current, field):
            continue
        if not permissions.has(forum, OPTION_VERBS[field]):
            raise ForbiddenException(f"You can't change {field} on this thread")
        changes[field] = value
    return current.model_copy(update=changes)


def check_thread_options(
    permissions: ForumPermissions, forum: Forum, options: Thread.Options
) -> None:
    """Raise if a new thread sets an option the principal may not set.

    Every option defaults to a falsy value, so "set" means truthy; that also
    treats an empty webhook string (what the form sends) as unset.
    """
    for field, verb in OPTION_VERBS.items():
        if getattr(options, field) and not permissions.has(forum, verb):
            raise ForbiddenException(f"You can't set {field} on this thread")
