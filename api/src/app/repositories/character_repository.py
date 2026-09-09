from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.models import Character, CharacterSheet, User


class CharacterRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def create(
        self,
        character_sheet_id: int,
        label: str,
        type: Character.Type = Character.Type.PC,
    ) -> Character:
        character = Character(
            user_id=self.principal.id,
            character_sheet_id=character_sheet_id,
            label=label,
            type=type,
        )
        self.db_session.add(character)
        await self.db_session.flush()

        return character

    async def get(self, id: int) -> Character | None:
        query = (
            select(Character)
            .where(Character.id == id)
            .options(
                selectinload(Character.character_sheet).options(
                    selectinload(CharacterSheet.creator),
                    selectinload(CharacterSheet.system),
                    undefer(CharacterSheet.layout),
                ),
            )
        )
        return await self.db_session.scalar(query)
