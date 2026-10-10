from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy import ScalarResult, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs import configs
from app.models import Character, Deck, Forum, Post, PostDraw, PostRoll, Thread, User
from app.repositories.character_repository import CharacterRepository


class PostRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def count_by_author(self, author_id: int) -> tuple[int, int]:
        """Returns (game_post_count, community_post_count) for a user."""
        result = await self.db_session.execute(
            select(
                func.count().filter(Forum.game_id.is_not(None)),
                func.count().filter(Forum.game_id.is_(None)),
            )
            .select_from(Post)
            .join(Thread, Post.thread_id == Thread.id)
            .join(Forum, Thread.forum_id == Forum.id)
            .where(
                Post.author_id == author_id,
                Post.state == Post.States.PUBLISHED,
                Post.deleted.is_(None),
            )
        )
        game_post_count, community_post_count = result.one()
        return game_post_count or 0, community_post_count or 0

    async def count_by_thread(self, thread_id: int) -> int:
        return (
            await self.db_session.scalar(
                select(func.count()).where(
                    Post.thread_id == thread_id,
                    Post.state == Post.States.PUBLISHED,
                    Post.deleted.is_(None),
                )
            )
            or 0
        )

    async def get(self, post_id: int) -> Post | None:
        post = await self.db_session.scalar(
            select(Post)
            .where(Post.id == post_id, Post.deleted.is_(None))
            .options(selectinload(Post.posted_as).selectinload(Character.avatars))
            .limit(1)
        )
        return post

    async def get_latest_by_author(self, thread_id: int, author_id: int) -> Post | None:
        """The author's most recent published post in the thread."""
        return await self.db_session.scalar(
            select(Post)
            .where(
                Post.thread_id == thread_id,
                Post.author_id == author_id,
                Post.state == Post.States.PUBLISHED,
                Post.deleted.is_(None),
            )
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(1)
        )

    async def get_page_number(
        self, post: Post, limit: int = configs.PAGINATE_PER_PAGE
    ) -> int:
        if post.published_at is None:
            return 1

        position = (
            await self.db_session.scalar(
                select(func.count()).where(
                    Post.thread_id == post.thread_id,
                    Post.state == Post.States.PUBLISHED,
                    Post.published_at < post.published_at,
                    Post.deleted.is_(None),
                )
            )
            or 0
        )
        return position // limit + 1

    async def get_first_published_after(
        self, thread_id: int, after: datetime | None
    ) -> Post | None:
        """The thread's earliest published post past ``after`` (any, if None)."""
        query = select(Post).where(
            Post.thread_id == thread_id,
            Post.state == Post.States.PUBLISHED,
            Post.deleted.is_(None),
        )
        if after is not None:
            query = query.where(Post.published_at > after)
        return await self.db_session.scalar(
            query.order_by(Post.published_at, Post.id).limit(1)
        )

    async def get_all(
        self, thread_id: int, page: int = 1, limit: int = configs.PAGINATE_PER_PAGE
    ) -> ScalarResult[Post]:
        return await self.db_session.scalars(
            select(Post)
            .where(
                Post.thread_id == thread_id,
                Post.state == Post.States.PUBLISHED,
                Post.deleted.is_(None),
            )
            .options(
                selectinload(Post.author).selectinload(User.meta),
                selectinload(Post.posted_as).selectinload(Character.avatars),
            )
            .order_by(Post.published_at)
            .limit(limit)
            .offset((page - 1) * limit)
        )

    async def create(
        self,
        thread_id: int,
        author_id: int,
        title: str,
        body: dict,
        state: Post.States = Post.States.DRAFT,
        posted_as_id: int | None = None,
    ) -> Post:
        post = Post(
            thread_id=thread_id,
            author_id=author_id,
            title=title,
            body=body,
            state=state,
            posted_as_id=posted_as_id,
        )
        self.db_session.add(post)
        await self.db_session.flush()
        # Loaded now (avatars too), as a new post can't lazy-load it later.
        await self.set_posted_as(post, posted_as_id)
        return post

    async def set_posted_as(self, post: Post, character_id: int | None) -> Post:
        """Post as the character (``None`` for as the author). Not validated."""
        character = (
            await CharacterRepository(
                self.db_session, principal=self.principal
            ).get_with_avatars(character_id)
            if character_id is not None
            else None
        )
        post.posted_as = character
        post.posted_as_id = character_id
        await self.db_session.flush()
        return post

    async def update(self, post: Post, title: str, body: dict) -> Post:
        post.title = title
        post.body = body
        self.db_session.add(post)
        await self.db_session.flush()
        return post

    async def get_rolls(self, post_ids: Collection[int]) -> dict[int, list[PostRoll]]:
        """The rolls on each post (oldest first), in one query."""
        rolls: dict[int, list[PostRoll]] = {post_id: [] for post_id in post_ids}
        if not rolls:
            return rolls
        result = await self.db_session.scalars(
            select(PostRoll).where(PostRoll.post_id.in_(rolls)).order_by(PostRoll.id)
        )
        for roll in result:
            rolls[roll.post_id].append(roll)
        return rolls

    async def get_draws(self, post_ids: Collection[int]) -> dict[int, list[PostDraw]]:
        """The draws on each post (oldest first), in one query."""
        draws: dict[int, list[PostDraw]] = {post_id: [] for post_id in post_ids}
        if not draws:
            return draws
        result = await self.db_session.scalars(
            select(PostDraw).where(PostDraw.post_id.in_(draws)).order_by(PostDraw.id)
        )
        for draw in result:
            draws[draw.post_id].append(draw)
        return draws

    async def add_roll(
        self,
        post_id: int,
        type: str,
        reason: str,
        input: str,
        options: dict,
        result: dict,
        hide_reason: bool,
        hide_dice: bool,
        hide_result: bool,
    ) -> PostRoll:
        roll = PostRoll(
            post_id=post_id,
            type=type,
            reason=reason,
            input=input,
            options=options,
            result=result,
            hide_reason=hide_reason,
            hide_dice=hide_dice,
            hide_result=hide_result,
        )
        self.db_session.add(roll)
        await self.db_session.flush()
        return roll

    async def add_draw(
        self, post_id: int, deck: Deck, reason: str, cards: list[int]
    ) -> PostDraw:
        draw = PostDraw(
            post_id=post_id,
            deck_id=deck.id,
            deck_label=deck.label,
            deck_type=deck.type_id,
            reason=reason,
            cards=cards,
            revealed=[False] * len(cards),
        )
        self.db_session.add(draw)
        await self.db_session.flush()
        return draw

    async def set_roll_visibility(
        self, roll: PostRoll, hide_reason: bool, hide_dice: bool, hide_result: bool
    ) -> PostRoll:
        roll.hide_reason = hide_reason
        roll.hide_dice = hide_dice
        roll.hide_result = hide_result
        await self.db_session.flush()
        return roll

    async def get_draw(self, draw_id: int) -> PostDraw | None:
        return await self.db_session.get(PostDraw, draw_id)

    async def set_card_revealed(
        self, draw: PostDraw, index: int, revealed: bool
    ) -> PostDraw:
        # Reassign rather than mutate: plain JSON columns don't track in-place edits.
        draw.revealed = [
            revealed if i == index else value for i, value in enumerate(draw.revealed)
        ]
        await self.db_session.flush()
        return draw

    async def delete(self, post: Post):
        post.deleted = datetime.now(UTC)
        self.db_session.add(post)
        await self.db_session.flush()
