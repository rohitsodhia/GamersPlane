import random
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundException, ValidationError
from app.models import Deck, DeckPermission, DeckType, User


class DeckRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def create(
        self, game_id: int, label: str, type: str, permissions: list[int]
    ) -> Deck:
        deck_type = await self._get_deck_type_or_404(type)

        deck = Deck(
            game_id=game_id,
            label=label,
            type_id=deck_type.short,
            order=self._shuffled_order(deck_type),
            position=0,
            last_shuffled=datetime.now(timezone.utc),
        )
        self.db_session.add(deck)
        await self.db_session.flush()

        for user_id in set(permissions):
            self.db_session.add(DeckPermission(user_id=user_id, deck_id=deck.id))

        return deck

    async def update(
        self, deck: Deck, label: str, type: str, permissions: list[int]
    ) -> Deck:
        if deck.type_id != type:
            deck_type = await self._get_deck_type_or_404(type)
            deck.type_id = deck_type.short
            deck.order = self._shuffled_order(deck_type)
            deck.position = 0
            deck.last_shuffled = datetime.now(timezone.utc)

        deck.label = label

        await self.db_session.execute(
            delete(DeckPermission).where(DeckPermission.deck_id == deck.id)
        )
        for user_id in set(permissions):
            self.db_session.add(DeckPermission(user_id=user_id, deck_id=deck.id))

        await self.db_session.flush()
        await self.db_session.refresh(deck, attribute_names=["permissions"])

        return deck

    async def _get_deck_type_or_404(self, type: str) -> DeckType:
        deck_type = await self.db_session.get(DeckType, type)
        if not deck_type:
            raise NotFoundException("Deck type not found")
        return deck_type

    def _shuffled_order(self, deck_type: DeckType) -> list[int]:
        deck_order = list(range(deck_type.deck_size))
        random.shuffle(deck_order)
        return deck_order

    async def get_by_id(self, deck_id: int):
        return await self.db_session.scalar(
            select(Deck)
            .where(Deck.id == deck_id)
            .options(selectinload(Deck.permissions))
        )

    async def get_for_update(self, deck_id: int) -> Deck | None:
        """Fetch a deck with its row locked until the request's transaction ends.

        Lock before reading ``position`` for a draw, so concurrent draws serialize
        instead of taking the same cards. ``populate_existing`` makes sure an
        already-loaded copy is refreshed to the locked row's values.
        """
        return await self.db_session.scalar(
            select(Deck)
            .where(Deck.id == deck_id)
            # of=Deck: the deck type is outer-joined, and that side can't be locked.
            .with_for_update(of=Deck)
            .execution_options(populate_existing=True)
        )

    async def can_draw(self, deck_id: int, user_id: int) -> bool:
        """Whether the user has been given draw access to the deck (GMs aside)."""
        return (
            await self.db_session.scalar(
                select(DeckPermission.user_id).where(
                    DeckPermission.deck_id == deck_id,
                    DeckPermission.user_id == user_id,
                )
            )
            is not None
        )

    async def draw(self, deck: Deck, count: int) -> list[int]:
        """Take the next ``count`` cards off the deck and advance its position.

        The deck must have been locked with ``get_for_update`` in this
        transaction. Raises ``ValidationError`` if fewer than ``count`` cards remain.
        """
        remaining = len(deck.order) - deck.position
        if count > remaining:
            raise ValidationError(
                f"Not enough cards left in {deck.label} "
                f"({remaining} remaining, {count} requested)"
            )
        cards = deck.order[deck.position : deck.position + count]
        deck.position += count
        await self.db_session.flush()
        return cards

    async def get_all_for_game(self, game_id: int):
        return await self.db_session.scalars(
            select(Deck)
            .where(Deck.game_id == game_id)
            .options(selectinload(Deck.permissions))
        )

    async def get_deck_types(self):
        return await self.db_session.scalars(select(DeckType))

    async def shuffle(self, deck_id: int):
        deck = await self.get_by_id(deck_id)
        if not deck:
            raise NotFoundException("Deck not found")

        deck.order = self._shuffled_order(
            await self._get_deck_type_or_404(deck.type_id)
        )
        deck.last_shuffled = datetime.now(timezone.utc)
        deck.position = 0
        await self.db_session.flush()

    async def delete(self, deck_id: int):
        await self.db_session.execute(delete(Deck).where(Deck.id == deck_id))
        await self.db_session.flush()
