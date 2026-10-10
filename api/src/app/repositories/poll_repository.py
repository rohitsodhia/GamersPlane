from collections.abc import Collection

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Poll, PollOption, PollVote, User
from app.threads.poll_schemas import PollInput


class PollRepository:
    def __init__(self, db_session: AsyncSession, principal: User | None):
        self.db_session = db_session
        self.principal = principal

    async def get(self, thread_id: int) -> Poll | None:
        return await self.db_session.get(Poll, thread_id)

    async def get_options(self, thread_id: int) -> list[PollOption]:
        """The poll's options in display order."""
        options = await self.db_session.scalars(
            select(PollOption)
            .where(PollOption.thread_id == thread_id)
            .order_by(PollOption.position, PollOption.id)
        )
        return list(options)

    async def vote_counts(self, thread_id: int) -> dict[int, int]:
        """Votes per option id; options nobody voted for are absent."""
        rows = await self.db_session.execute(
            select(PollVote.option_id, func.count())
            .join(PollOption, PollOption.id == PollVote.option_id)
            .where(PollOption.thread_id == thread_id)
            .group_by(PollVote.option_id)
        )
        return {option_id: count for option_id, count in rows}

    async def total_voters(self, thread_id: int) -> int:
        return (
            await self.db_session.scalar(
                select(func.count(func.distinct(PollVote.user_id)))
                .join(PollOption, PollOption.id == PollVote.option_id)
                .where(PollOption.thread_id == thread_id)
            )
            or 0
        )

    async def user_votes(self, thread_id: int, user_id: int) -> list[int]:
        option_ids = await self.db_session.scalars(
            select(PollVote.option_id)
            .join(PollOption, PollOption.id == PollVote.option_id)
            .where(PollOption.thread_id == thread_id, PollVote.user_id == user_id)
            .order_by(PollVote.option_id)
        )
        return list(option_ids)

    async def max_votes_per_user(
        self, thread_id: int, excluding_option_ids: Collection[int] = ()
    ) -> int:
        """The most options any one voter has picked, ignoring votes on
        ``excluding_option_ids``."""
        per_user = (
            select(func.count().label("votes"))
            .select_from(PollVote)
            .join(PollOption, PollOption.id == PollVote.option_id)
            .where(
                PollOption.thread_id == thread_id,
                PollVote.option_id.not_in(excluding_option_ids),
            )
            .group_by(PollVote.user_id)
            .subquery()
        )
        return await self.db_session.scalar(select(func.max(per_user.c.votes))) or 0

    async def create(self, thread_id: int, data: PollInput) -> Poll:
        poll = Poll(
            thread_id=thread_id,
            question=data.question,
            options_per_user=data.options_per_user,
            allow_revoting=data.allow_revoting,
        )
        self.db_session.add(poll)
        # The options reference the poll's row.
        await self.db_session.flush()
        self.db_session.add_all(
            PollOption(thread_id=thread_id, text=option.text, position=position)
            for position, option in enumerate(data.options)
        )
        await self.db_session.flush()
        return poll

    async def apply_edit(
        self, poll: Poll, options: list[PollOption], data: PollInput
    ) -> Poll:
        """Make the poll match ``data``. ``options`` are its current options.

        Options with an id keep their votes and get the new text; options left
        out are deleted along with their votes. Positions follow the list order.
        """
        poll.question = data.question
        poll.options_per_user = data.options_per_user
        poll.allow_revoting = data.allow_revoting

        by_id = {option.id: option for option in options}
        kept_ids = {option.id for option in data.options if option.id is not None}
        removed = [option for option in options if option.id not in kept_ids]
        if removed:
            await self.db_session.execute(
                delete(PollOption)
                .where(PollOption.id.in_([option.id for option in removed]))
                .execution_options(synchronize_session="fetch")
            )

        for position, option_data in enumerate(data.options):
            if option_data.id is None:
                self.db_session.add(
                    PollOption(
                        thread_id=poll.thread_id,
                        text=option_data.text,
                        position=position,
                    )
                )
            else:
                option = by_id[option_data.id]
                option.text = option_data.text
                option.position = position
        await self.db_session.flush()
        return poll

    async def delete(self, poll: Poll) -> None:
        """Remove the poll with its options and votes."""
        option_ids = select(PollOption.id).where(PollOption.thread_id == poll.thread_id)
        await self.db_session.execute(
            delete(PollVote)
            .where(PollVote.option_id.in_(option_ids))
            .execution_options(synchronize_session="fetch")
        )
        await self.db_session.execute(
            delete(PollOption)
            .where(PollOption.thread_id == poll.thread_id)
            .execution_options(synchronize_session="fetch")
        )
        await self.db_session.execute(
            delete(Poll)
            .where(Poll.thread_id == poll.thread_id)
            .execution_options(synchronize_session="fetch")
        )

    async def replace_votes(
        self, thread_id: int, user_id: int, option_ids: Collection[int]
    ) -> None:
        """Make ``option_ids`` the user's only votes in this poll."""
        poll_options = select(PollOption.id).where(PollOption.thread_id == thread_id)
        await self.db_session.execute(
            delete(PollVote)
            .where(PollVote.user_id == user_id, PollVote.option_id.in_(poll_options))
            .execution_options(synchronize_session="fetch")
        )
        self.db_session.add_all(
            PollVote(user_id=user_id, option_id=option_id) for option_id in option_ids
        )
        await self.db_session.flush()
