from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FAQ


class FAQRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get(self, faq_id: int) -> FAQ | None:
        return await self.db_session.get(FAQ, faq_id)

    async def get_all(self) -> list[FAQ]:
        """Every FAQ, ordered by position (callers group them by category)."""
        faqs = await self.db_session.scalars(
            select(FAQ).order_by(FAQ.category, FAQ.order, FAQ.id)
        )
        return list(faqs.all())

    async def _next_order(self, category: FAQ.Categories) -> int:
        highest = await self.db_session.scalar(
            select(func.max(FAQ.order)).where(FAQ.category == category)
        )
        return (highest or 0) + 1

    async def _close_gap(self, category: FAQ.Categories, order: int) -> None:
        await self.db_session.execute(
            update(FAQ)
            .where(FAQ.category == category, FAQ.order > order)
            .values(order=FAQ.order - 1)
            .execution_options(synchronize_session="fetch")
        )

    async def add(self, category: FAQ.Categories, question: str, answer: dict) -> FAQ:
        """Create a FAQ at the end of its category."""
        faq = FAQ(
            category=category,
            question=question,
            answer=answer,
            order=await self._next_order(category),
        )
        self.db_session.add(faq)
        await self.db_session.flush()
        return faq

    async def update(
        self,
        faq: FAQ,
        category: FAQ.Categories,
        question: str,
        answer: dict,
    ) -> FAQ:
        """Change a FAQ. A new category puts it at the end of that category and
        closes the gap it leaves behind."""
        if category != faq.category:
            old_category, old_order = faq.category, faq.order
            # Computed before the change so autoflush can't count the FAQ itself.
            # It moves first so the old category's gap-closing can't touch it.
            new_order = await self._next_order(category)
            faq.category = category
            faq.order = new_order
            await self.db_session.flush()
            await self._close_gap(old_category, old_order)
        faq.question = question
        faq.answer = answer
        await self.db_session.flush()
        return faq

    async def delete(self, faq: FAQ) -> None:
        category, order = faq.category, faq.order
        await self.db_session.delete(faq)
        await self.db_session.flush()
        await self._close_gap(category, order)

    async def move(self, faq: FAQ, direction: Literal["up", "down"]) -> None:
        """Swap with the neighbour in its category; a no-op at the end."""
        target_order = faq.order - 1 if direction == "up" else faq.order + 1
        neighbour = await self.db_session.scalar(
            select(FAQ).where(FAQ.category == faq.category, FAQ.order == target_order)
        )
        if neighbour is None:
            return
        neighbour.order, faq.order = faq.order, neighbour.order
        await self.db_session.flush()
