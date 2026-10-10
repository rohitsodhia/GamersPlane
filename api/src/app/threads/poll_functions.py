from sqlalchemy import select

from app.exceptions import ForbiddenException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Forum, Poll, PollOption, Post, Thread, User
from app.repositories import PollRepository
from app.threads.poll_schemas import PollData, PollInput, PollOptionData


def require_add_poll(permissions: ForumPermissions, forum: Forum) -> None:
    if not permissions.has(forum, Verbs.FORUM_ADD_POLL):
        raise ForbiddenException("You can't add or change polls in this forum")


async def check_poll_input(
    poll_repository: PollRepository, poll: Poll | None, data: PollInput
) -> list[PollOption]:
    """Raise if ``data`` can't be applied to the thread's poll (``None`` if it has
    none yet); otherwise return the poll's current options, empty for no poll.

    An option id must be one of the poll's own, and ``options_per_user`` can't drop
    below what a voter has already picked among the options that stay.
    """
    given_ids = {option.id for option in data.options if option.id is not None}
    if poll is None:
        if given_ids:
            raise ValidationError("New poll options can't have ids")
        return []

    current = await poll_repository.get_options(poll.thread_id)
    current_ids = {option.id for option in current}
    if not given_ids <= current_ids:
        raise ValidationError("An option isn't part of this thread's poll")
    most_picked = await poll_repository.max_votes_per_user(
        poll.thread_id, excluding_option_ids=current_ids - given_ids
    )
    if data.options_per_user < most_picked:
        raise ValidationError(
            f"Someone has already voted for {most_picked} options, so each person "
            "must be allowed at least that many"
        )
    return current


async def build_poll_data(
    poll_repository: PollRepository,
    thread: Thread,
    permissions: ForumPermissions,
    principal: User | None,
    force_results: bool = False,
) -> PollData | None:
    """The thread's poll as ``principal`` may see it, or ``None`` without one.

    Counts are shown to anyone who has voted, to the thread's creator, and to
    everyone once the thread is locked (or always, with ``force_results``).
    """
    poll = await poll_repository.get(thread.id)
    if poll is None:
        return None

    my_votes = (
        await poll_repository.user_votes(thread.id, principal.id) if principal else []
    )
    voted = bool(my_votes)
    locked = thread.options.locked
    # Queried rather than read off ``thread.first_post``, which may not be loaded.
    creator_id = await poll_repository.db_session.scalar(
        select(Post.author_id).where(Post.id == thread.first_post_id)
    )
    is_creator = principal is not None and creator_id == principal.id
    show_results = force_results or voted or is_creator or locked

    counts = await poll_repository.vote_counts(thread.id) if show_results else {}
    options = await poll_repository.get_options(thread.id)
    return PollData(
        question=poll.question,
        options_per_user=poll.options_per_user,
        allow_revoting=poll.allow_revoting,
        options=[
            PollOptionData(
                id=option.id,
                text=option.text,
                votes=counts.get(option.id, 0) if show_results else None,
            )
            for option in options
        ],
        my_votes=my_votes,
        voted=voted,
        can_vote=principal is not None
        and permissions.has(thread.forum, Verbs.FORUM_WRITE)
        and not locked
        and (not voted or poll.allow_revoting),
        show_results=show_results,
        total_voters=await poll_repository.total_voters(thread.id)
        if show_results
        else None,
    )
