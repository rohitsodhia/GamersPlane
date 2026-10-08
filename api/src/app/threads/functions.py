from app.exceptions import ForbiddenException
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Forum, Post, Thread
from app.threads import schemas

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
