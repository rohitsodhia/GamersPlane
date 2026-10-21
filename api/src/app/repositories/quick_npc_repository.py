from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException
from app.models import NPCImage, QuickNPC, User


@dataclass(frozen=True)
class NPCOwner:
    """Whose library a quick NPC or image belongs to: a game's (shared by its
    players) or a user's. Exactly one of the two is set."""

    game_id: int | None = None
    user_id: int | None = None

    @classmethod
    def game(cls, game_id: int) -> Self:
        return cls(game_id=game_id)

    @classmethod
    def user(cls, user_id: int) -> Self:
        return cls(user_id=user_id)

    def clause(self, model: type[QuickNPC] | type[NPCImage]) -> ColumnElement[bool]:
        """The ``WHERE`` condition for rows of ``model`` this owner holds."""
        if self.game_id is not None:
            return model.game_id == self.game_id
        return model.user_id == self.user_id

    def owns(self, row: QuickNPC | NPCImage) -> bool:
        return row.game_id == self.game_id and row.user_id == self.user_id


class QuickNPCRepository:
    """A quick NPC image library and its NPCs (name + optional image), for one
    ``NPCOwner`` at a time.

    ``QuickNPC`` has no ``SoftDeleteMixin`` (old posts must still load a deleted
    NPC), so every lookup here filters ``deleted IS NULL`` itself.
    """

    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def get_images(self, owner: NPCOwner) -> list[NPCImage]:
        """The owner's library images, newest first."""
        result = await self.db_session.scalars(
            select(NPCImage)
            .where(owner.clause(NPCImage))
            .order_by(NPCImage.created_at.desc(), NPCImage.id.desc())
        )
        return list(result)

    async def get_image(self, image_id: int) -> NPCImage | None:
        return await self.db_session.get(NPCImage, image_id)

    async def create_image(self, owner: NPCOwner, ext: str) -> NPCImage:
        image = NPCImage(
            game_id=owner.game_id,
            user_id=owner.user_id,
            ext=ext,
            uploaded_by=self.principal.id,
        )
        self.db_session.add(image)
        await self.db_session.flush()
        return image

    async def remove_image(self, image: NPCImage) -> None:
        """Delete a library image. NPCs using it lose their image; one that would
        then duplicate a live NPC with the same name and no image is deleted."""
        using = await self.db_session.scalars(
            select(QuickNPC).where(
                QuickNPC.image_id == image.id, QuickNPC.deleted.is_(None)
            )
        )
        for npc in list(using):
            owner = NPCOwner(game_id=npc.game_id, user_id=npc.user_id)
            if await self.find_live(owner, npc.name, None) is not None:
                npc.deleted = datetime.now(UTC)
            npc.image = None
            await self.db_session.flush()
        await self.db_session.delete(image)
        await self.db_session.flush()

    async def get_npcs(self, owner: NPCOwner) -> list[QuickNPC]:
        """The owner's live NPCs, most recently used first, then by name."""
        result = await self.db_session.scalars(
            select(QuickNPC)
            .where(owner.clause(QuickNPC), QuickNPC.deleted.is_(None))
            .order_by(
                QuickNPC.last_used_at.desc().nulls_last(),
                QuickNPC.name,
                QuickNPC.id,
            )
        )
        return list(result)

    async def get_npc(self, npc_id: int) -> QuickNPC | None:
        """A live NPC by id."""
        return await self.db_session.scalar(
            select(QuickNPC).where(QuickNPC.id == npc_id, QuickNPC.deleted.is_(None))
        )

    async def get_many(self, npc_ids: list[int]) -> list[QuickNPC]:
        """The NPCs with these ids, deleted ones included (old posts still show
        their speakers)."""
        if not npc_ids:
            return []
        result = await self.db_session.scalars(
            select(QuickNPC).where(QuickNPC.id.in_(npc_ids))
        )
        return list(result)

    async def live_ids(self, owner: NPCOwner, npc_ids: list[int]) -> set[int]:
        """Which of ``npc_ids`` are live NPCs in the owner's library."""
        if not npc_ids:
            return set()
        result = await self.db_session.scalars(
            select(QuickNPC.id).where(
                owner.clause(QuickNPC),
                QuickNPC.id.in_(npc_ids),
                QuickNPC.deleted.is_(None),
            )
        )
        return set(result)

    async def find_live(
        self, owner: NPCOwner, name: str, image_id: int | None
    ) -> QuickNPC | None:
        """The owner's live NPC with exactly this name and image (``None`` matches
        no image)."""
        return await self.db_session.scalar(
            select(QuickNPC).where(
                owner.clause(QuickNPC),
                QuickNPC.name == name,
                QuickNPC.image_id.is_not_distinct_from(image_id),
                QuickNPC.deleted.is_(None),
            )
        )

    async def get_or_create(
        self, owner: NPCOwner, name: str, image: NPCImage | None
    ) -> QuickNPC:
        """The live NPC for this name + image, made if there isn't one yet."""
        image_id = image.id if image is not None else None
        existing = await self.find_live(owner, name, image_id)
        if existing is not None:
            return existing

        npc = QuickNPC(
            game_id=owner.game_id,
            user_id=owner.user_id,
            name=name,
            image=image,
            created_by=self.principal.id,
        )
        try:
            # A savepoint, so losing a race to the unique index doesn't poison the
            # request's transaction.
            async with self.db_session.begin_nested():
                self.db_session.add(npc)
                await self.db_session.flush()
        except IntegrityError:
            existing = await self.find_live(owner, name, image_id)
            if existing is None:
                raise
            return existing
        return npc

    async def update(
        self,
        npc: QuickNPC,
        name: str,
        image: NPCImage | None,
    ) -> QuickNPC:
        """Rename and/or re-image the NPC. Raises ``ConflictException`` if another
        live NPC already has the resulting pair."""
        image_id = image.id if image is not None else None
        owner = NPCOwner(game_id=npc.game_id, user_id=npc.user_id)
        clash = await self.find_live(owner, name, image_id)
        if clash is not None and clash.id != npc.id:
            raise ConflictException("An NPC with that name and image already exists")

        npc.name = name
        npc.image = image
        await self.db_session.flush()
        return npc

    async def mark_used(self, npc: QuickNPC) -> None:
        npc.last_used_at = datetime.now(UTC)
        await self.db_session.flush()

    async def delete(self, npc: QuickNPC) -> None:
        npc.deleted = datetime.now(UTC)
        await self.db_session.flush()
