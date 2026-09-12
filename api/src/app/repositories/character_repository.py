from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.models import Character, CharacterAvatar, CharacterSheet, User


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

    async def update(self, character: Character, values: dict) -> Character:
        character.values = values
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
                selectinload(Character.avatars),
            )
        )
        return await self.db_session.scalar(query)

    async def add_avatar(self, character: Character, ext: str) -> CharacterAvatar:
        avatar = CharacterAvatar(
            character_id=character.id,
            ext=ext,
            is_primary=not character.avatars,
        )
        self.db_session.add(avatar)
        character.avatars.append(avatar)
        await self.db_session.flush()

        return avatar

    async def delete_avatar(
        self, character: Character, avatar_id: int
    ) -> CharacterAvatar | None:
        avatar = next((a for a in character.avatars if a.id == avatar_id), None)
        if avatar is None:
            return None

        character.avatars.remove(avatar)
        await self.db_session.delete(avatar)
        await self.db_session.flush()

        if avatar.is_primary and character.avatars:
            character.avatars[0].is_primary = True
            await self.db_session.flush()

        return avatar

    async def set_primary_avatar(
        self, character: Character, avatar_id: int
    ) -> CharacterAvatar | None:
        target = next((a for a in character.avatars if a.id == avatar_id), None)
        if target is None:
            return None

        for avatar in character.avatars:
            avatar.is_primary = avatar.id == avatar_id

        await self.db_session.flush()

        return target
