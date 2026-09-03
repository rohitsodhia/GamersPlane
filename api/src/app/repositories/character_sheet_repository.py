from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CharacterSheet, User


class CharacterSheetRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def create(self, label: str, system_id: str) -> CharacterSheet:
        char_sheet = CharacterSheet(
            creator_id=self.principal.id, label=label, system_id=system_id
        )
        self.db_session.add(char_sheet)
        await self.db_session.flush()

        return char_sheet
