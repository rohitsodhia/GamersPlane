from datetime import UTC, datetime

from sqlalchemy import ScalarResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.configs import configs
from app.models import (
    Character,
    CharacterAvatar,
    CharacterSheet,
    FavoriteCharacter,
    System,
    User,
)


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

    async def update(
        self,
        character: Character,
        label: str | None = None,
        type: Character.Type | None = None,
        values: dict | None = None,
    ) -> Character:
        if label is not None:
            character.label = label
        if type is not None:
            character.type = type
        if values is not None:
            character.values = values
        await self.db_session.flush()

        return character

    async def toggle_library(self, character: Character) -> None:
        character.in_library = not character.in_library
        await self.db_session.flush()

    async def delete(self, character: Character) -> None:
        character.deleted = datetime.now(UTC)
        character.in_library = False
        await self.db_session.execute(
            delete(FavoriteCharacter).where(
                FavoriteCharacter.character_id == character.id
            )
        )
        await self.db_session.flush()

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

    def _list_query(
        self,
        search: str | None = None,
        type: Character.Type | None = None,
        system_id: str | None = None,
    ):
        query = (
            select(Character)
            .where(Character.user_id == self.principal.id)
            .join(Character.character_sheet)
        )
        if search:
            query = query.where(Character.label.ilike(f"%{search}%"))
        if type:
            query = query.where(Character.type == type)
        if system_id:
            query = query.where(CharacterSheet.system_id == system_id)
        return query

    async def get_all(
        self,
        search: str | None = None,
        type: Character.Type | None = None,
        system_id: str | None = None,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
    ) -> ScalarResult[Character]:
        query = (
            self._list_query(search, type, system_id)
            .join(CharacterSheet.system)
            .order_by(System.sort_name.asc(), Character.label.asc())
            .options(
                selectinload(Character.character_sheet).options(
                    selectinload(CharacterSheet.creator),
                    selectinload(CharacterSheet.system),
                    undefer(CharacterSheet.layout),
                ),
                selectinload(Character.avatars),
            )
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return await self.db_session.scalars(query)

    async def count_all(
        self,
        search: str | None = None,
        type: Character.Type | None = None,
        system_id: str | None = None,
    ) -> int:
        query = self._list_query(search, type, system_id)
        return (
            await self.db_session.scalar(
                select(func.count()).select_from(query.subquery())
            )
            or 0
        )

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
