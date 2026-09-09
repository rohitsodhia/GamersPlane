from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.character_sheets.defaults import default_sheet_layout
from app.models import CharacterSheet, CharacterSheetFavorite, User


class CharacterSheetRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def create(
        self, name: str, system_id: str, layout: dict | None = None
    ) -> CharacterSheet:
        char_sheet = CharacterSheet(
            creator_id=self.principal.id,
            name=name,
            system_id=system_id,
            layout=layout if layout is not None else default_sheet_layout(),
        )
        self.db_session.add(char_sheet)
        await self.db_session.flush()

        return char_sheet

    async def update(
        self, char_sheet: CharacterSheet, *, layout: dict
    ) -> CharacterSheet:
        char_sheet.layout = layout
        await self.db_session.flush()

        return char_sheet

    async def get_by_creator_id(self, creator_id: int) -> list[CharacterSheet]:
        query = (
            select(CharacterSheet)
            .where(CharacterSheet.creator_id == creator_id)
            .options(
                selectinload(CharacterSheet.creator),
                selectinload(CharacterSheet.system),
            )
        )
        return list(await self.db_session.scalars(query))

    async def get_favorited_by_user_id(self, user_id: int) -> list[CharacterSheet]:
        query = (
            select(CharacterSheet)
            .join(
                CharacterSheetFavorite,
                CharacterSheetFavorite.character_sheet_id == CharacterSheet.id,
            )
            .where(CharacterSheetFavorite.user_id == user_id)
            .options(
                selectinload(CharacterSheet.creator),
                selectinload(CharacterSheet.system),
            )
        )
        return list(await self.db_session.scalars(query))

    async def get(self, id: int) -> CharacterSheet | None:
        query = (
            select(CharacterSheet)
            .where(CharacterSheet.id == id)
            .options(
                selectinload(CharacterSheet.creator),
                selectinload(CharacterSheet.system),
                undefer(CharacterSheet.layout),
            )
        )
        return await self.db_session.scalar(query)
