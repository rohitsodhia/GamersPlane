from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Character, User


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
            character_sheet_id=character_sheet_id,
            label=label,
            type=type,
        )
        self.db_session.add(character)
        await self.db_session.flush()

        return character
