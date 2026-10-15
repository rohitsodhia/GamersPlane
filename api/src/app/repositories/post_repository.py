from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ScalarResult, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs import configs
from app.helpers.prose import prose_to_text
from app.helpers.sql import in_array
from app.models import (
    Character,
    Deck,
    Forum,
    Post,
    PostDraw,
    PostRoll,
    QuickNPC,
    Thread,
    User,
)
from app.repositories.character_repository import CharacterRepository


# Wrap the matched words in a search snippet. Private-use characters rather than
# markup, so the snippet is plain text that can't carry HTML; callers split on
# them (see ``split_snippet``).
SNIPPET_MATCH_START = "\ue000"
SNIPPET_MATCH_END = "\ue001"
# The most matches a search counts; past it the response says the count is capped.
SEARCH_COUNT_CAP = 1000
_HEADLINE_OPTIONS = (
    f"StartSel={SNIPPET_MATCH_START}, StopSel={SNIPPET_MATCH_END}, "
    'MaxWords=35, MinWords=15, MaxFragments=2, FragmentDelimiter=" ... "'
)


@dataclass
class PostSearchResult:
    post_id: int
    thread_id: int
    title: str
    published_at: datetime
    author_id: int
    author_username: str
    forum_id: int
    forum_title: str
    game_id: int | None
    rank: float
    # The matching part of the post's text, matches wrapped in the markers above.
    snippet: str


class PostRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    @staticmethod
    def _search_matches(tsquery, game_id: int | None) -> tuple:
        """The conditions for a live, published post matching the query (in the
        game's forums, if given), over ``Post`` joined to ``Thread`` and ``Forum``."""
        return (
            Post.state == Post.States.PUBLISHED,
            Post.deleted.is_(None),
            Thread.deleted.is_(None),
            Post.search_tsv.bool_op("@@")(tsquery),
            *((Forum.game_id == game_id,) if game_id is not None else ()),
        )

    async def search_forum_ids(self, text: str, game_id: int | None = None) -> set[int]:
        """The forums holding at least one post that ``search`` would match. Check
        the principal's access to just these before searching."""
        tsquery = func.websearch_to_tsquery("english", text)
        return set(
            await self.db_session.scalars(
                select(Thread.forum_id)
                .select_from(Post)
                .join(Thread, Post.thread_id == Thread.id)
                .join(Forum, Thread.forum_id == Forum.id)
                .where(*self._search_matches(tsquery, game_id))
                .distinct()
            )
        )

    async def search(
        self,
        text: str,
        forum_ids: Collection[int],
        game_id: int | None = None,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
    ) -> tuple[list[PostSearchResult], int, bool]:
        """A page of the published, live posts in ``forum_ids`` (narrowed to the
        game's forums with ``game_id``) matching ``text``, best match first, the
        number of matches, and whether that count stopped at ``SEARCH_COUNT_CAP``
        (the real total is higher).

        ``text`` is parsed by ``websearch_to_tsquery`` (quoted phrases, ``or``,
        ``-exclusion``), which never raises on odd input.
        """
        if not forum_ids:
            return [], 0, False
        tsquery = func.websearch_to_tsquery("english", text)
        matching = (
            in_array(Thread.forum_id, forum_ids),
            *self._search_matches(tsquery, game_id),
        )
        # One past the cap, to tell "exactly the cap" from "more than the cap".
        capped_matches = (
            select(Post.id)
            .join(Thread, Post.thread_id == Thread.id)
            .join(Forum, Thread.forum_id == Forum.id)
            .where(*matching)
            .limit(SEARCH_COUNT_CAP + 1)
        )
        found = (
            await self.db_session.scalar(
                select(func.count()).select_from(capped_matches.subquery())
            )
            or 0
        )
        count = min(found, SEARCH_COUNT_CAP)
        rank = func.ts_rank(Post.search_tsv, tsquery).label("rank")
        rows = (
            await self.db_session.execute(
                select(
                    Post.id,
                    Post.thread_id,
                    Post.title,
                    Post.published_at,
                    Post.author_id,
                    User.username,
                    Forum.id.label("forum_id"),
                    Forum.title.label("forum_title"),
                    Forum.game_id,
                    rank,
                )
                .join(Thread, Post.thread_id == Thread.id)
                .join(Forum, Thread.forum_id == Forum.id)
                .join(User, Post.author_id == User.id)
                .where(*matching)
                .order_by(rank.desc(), Post.published_at.desc(), Post.id.desc())
                .limit(limit)
                .offset((page - 1) * limit)
            )
        ).all()

        # Headlines are slow, so they're made only for the page's posts.
        snippets = dict(
            (
                await self.db_session.execute(
                    select(
                        Post.id,
                        func.ts_headline(
                            "english", Post.body_text, tsquery, _HEADLINE_OPTIONS
                        ),
                    ).where(Post.id.in_([row.id for row in rows]))
                )
            ).all()
        )
        return (
            [
                PostSearchResult(
                    post_id=row.id,
                    thread_id=row.thread_id,
                    title=row.title,
                    published_at=row.published_at,
                    author_id=row.author_id,
                    author_username=row.username,
                    forum_id=row.forum_id,
                    forum_title=row.forum_title,
                    game_id=row.game_id,
                    rank=row.rank,
                    snippet=snippets[row.id],
                )
                for row in rows
            ],
            count,
            found > SEARCH_COUNT_CAP,
        )

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
            .options(
                selectinload(Post.author).selectinload(User.meta),
                selectinload(Post.posted_as).selectinload(Character.avatars),
            )
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
        posted_avatar_id: int | None = None,
        posted_npc: QuickNPC | None = None,
    ) -> Post:
        post = Post(
            thread_id=thread_id,
            author_id=author_id,
            title=title,
            body=body,
            body_text=prose_to_text(body),
            state=state,
            posted_as_id=posted_as_id,
            posted_avatar_id=posted_avatar_id,
            # Assigned as an object so it's loaded, as a new post can't lazy-load it.
            posted_npc=posted_npc,
        )
        self.db_session.add(post)
        await self.db_session.flush()
        # Loaded now (avatars too), as a new post can't lazy-load it later.
        await self.set_posted_as(post, posted_as_id, posted_avatar_id)
        return post

    async def set_posted_as(
        self, post: Post, character_id: int | None, avatar_id: int | None = None
    ) -> Post:
        """Post as the character (``None`` for as the author), showing the avatar
        (``None`` for its primary). Not validated."""
        character = (
            await CharacterRepository(
                self.db_session, principal=self.principal
            ).get_with_avatars(character_id)
            if character_id is not None
            else None
        )
        post.posted_as = character
        post.posted_as_id = character_id
        post.posted_avatar_id = avatar_id
        if character is not None:
            post.posted_npc = None
        await self.db_session.flush()
        return post

    async def set_posted_npc(self, post: Post, npc: QuickNPC | None) -> Post:
        """Post as the quick NPC (``None`` clears it). Posting as an NPC also clears
        the character and its avatar. Not validated."""
        post.posted_npc = npc
        if npc is not None:
            post.posted_as = None
            post.posted_avatar_id = None
        await self.db_session.flush()
        return post

    async def get_last_posts_as(
        self, game_id: int, author_id: int, character_ids: Collection[int]
    ) -> dict[int, Post]:
        """The author's most recent published post as each of the characters in
        any thread of the game's forums, in one query. Characters never posted
        as are left out."""
        if not character_ids:
            return {}
        latest = (
            select(
                Post.id,
                func.row_number()
                .over(
                    partition_by=Post.posted_as_id,
                    order_by=(Post.published_at.desc(), Post.id.desc()),
                )
                .label("rank"),
            )
            .join(Thread, Post.thread_id == Thread.id)
            .join(Forum, Thread.forum_id == Forum.id)
            .where(
                Forum.game_id == game_id,
                Post.author_id == author_id,
                Post.posted_as_id.in_(character_ids),
                Post.state == Post.States.PUBLISHED,
                Post.deleted.is_(None),
            )
            .subquery()
        )
        posts = await self.db_session.scalars(
            select(Post).join(latest, Post.id == latest.c.id).where(latest.c.rank == 1)
        )
        return {post.posted_as_id: post for post in posts if post.posted_as_id}

    async def update(self, post: Post, title: str, body: dict) -> Post:
        post.title = title
        post.body = body
        post.body_text = prose_to_text(body)
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
