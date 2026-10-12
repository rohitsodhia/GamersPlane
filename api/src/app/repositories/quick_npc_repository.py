from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException
from app.models import GameImage, GameNPC, User


class GameNPCRepository:
    """A game's quick NPC image library and its NPCs (name + optional image).

    ``GameNPC`` has no ``SoftDeleteMixin`` (old posts must still load a deleted
    NPC), so every lookup here filters ``deleted IS NULL`` itself.
    """

    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def get_images(self, game_id: int) -> list[GameImage]:
        """The game's library images, newest first."""
        result = await self.db_session.scalars(
            select(GameImage)
            .where(GameImage.game_id == game_id)
            .order_by(GameImage.created_at.desc(), GameImage.id.desc())
        )
        return list(result)

    async def get_image(self, image_id: int) -> GameImage | None:
        return await self.db_session.get(GameImage, image_id)

    async def create_image(self, game_id: int, ext: str) -> GameImage:
        image = GameImage(game_id=game_id, ext=ext, uploaded_by=self.principal.id)
        self.db_session.add(image)
        await self.db_session.flush()
        return image

    async def get_npcs(self, game_id: int) -> list[GameNPC]:
        """The game's live NPCs, most recently used first, then by name."""
        result = await self.db_session.scalars(
            select(GameNPC)
            .where(GameNPC.game_id == game_id, GameNPC.deleted.is_(None))
            .order_by(
                GameNPC.last_used_at.desc().nulls_last(),
                GameNPC.name,
                GameNPC.id,
            )
        )
        return list(result)

    async def get_npc(self, npc_id: int) -> GameNPC | None:
        """A live NPC by id."""
        return await self.db_session.scalar(
            select(GameNPC).where(GameNPC.id == npc_id, GameNPC.deleted.is_(None))
        )

    async def find_live(
        self, game_id: int, name: str, image_id: int | None
    ) -> GameNPC | None:
        """The live NPC with exactly this name and image (``None`` matches no image)."""
        return await self.db_session.scalar(
            select(GameNPC).where(
                GameNPC.game_id == game_id,
                GameNPC.name == name,
                GameNPC.image_id.is_not_distinct_from(image_id),
                GameNPC.deleted.is_(None),
            )
        )

    async def get_or_create(
        self, game_id: int, name: str, image: GameImage | None
    ) -> GameNPC:
        """The live NPC for this name + image, made if there isn't one yet."""
        image_id = image.id if image is not None else None
        existing = await self.find_live(game_id, name, image_id)
        if existing is not None:
            return existing

        npc = GameNPC(
            game_id=game_id,
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
            existing = await self.find_live(game_id, name, image_id)
            if existing is None:
                raise
            return existing
        return npc

    async def update(
        self,
        npc: GameNPC,
        name: str,
        image: GameImage | None,
    ) -> GameNPC:
        """Rename and/or re-image the NPC. Raises ``ConflictException`` if another
        live NPC already has the resulting pair."""
        image_id = image.id if image is not None else None
        clash = await self.find_live(npc.game_id, name, image_id)
        if clash is not None and clash.id != npc.id:
            raise ConflictException("An NPC with that name and image already exists")

        npc.name = name
        npc.image = image
        await self.db_session.flush()
        return npc

    async def mark_used(self, npc: GameNPC) -> None:
        npc.last_used_at = datetime.now(UTC)
        await self.db_session.flush()

    async def delete(self, npc: GameNPC) -> None:
        npc.deleted = datetime.now(UTC)
        await self.db_session.flush()
