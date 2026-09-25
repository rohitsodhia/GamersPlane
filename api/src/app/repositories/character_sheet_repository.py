import copy
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.character_sheets.defaults import default_sheet_layout
from app.character_sheets.layout_ids import mint_ids
from app.character_sheets.layout_validation import SCHEMA_VERSION
from app.configs import configs
from app.models import (
    CharacterSheet,
    CharacterSheetFavorite,
    CharacterSheetVersion,
    System,
    User,
)


class CharacterSheetRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def create(
        self, name: str, system_id: str, layout: dict | None = None
    ) -> CharacterSheet:
        """Create a sheet with its initial draft version."""
        char_sheet = CharacterSheet(
            creator_id=self.principal.id,
            name=name,
            system_id=system_id,
        )
        self.db_session.add(char_sheet)
        await self.db_session.flush()

        self.db_session.add(
            CharacterSheetVersion(
                character_sheet_id=char_sheet.id,
                schema_version=SCHEMA_VERSION,
                layout=layout
                if layout is not None
                else mint_ids(default_sheet_layout()),
            )
        )
        await self.db_session.flush()

        return char_sheet

    async def get_draft(self, char_sheet_id: int) -> CharacterSheetVersion | None:
        query = (
            select(CharacterSheetVersion)
            .where(CharacterSheetVersion.character_sheet_id == char_sheet_id)
            .where(CharacterSheetVersion.published_at.is_(None))
            .options(undefer(CharacterSheetVersion.layout))
        )
        return await self.db_session.scalar(query)

    async def get_latest_published(
        self, char_sheet_id: int
    ) -> CharacterSheetVersion | None:
        query = (
            select(CharacterSheetVersion)
            .where(CharacterSheetVersion.character_sheet_id == char_sheet_id)
            .where(CharacterSheetVersion.published_at.is_not(None))
            .order_by(CharacterSheetVersion.number.desc())
            .limit(1)
            .options(undefer(CharacterSheetVersion.layout))
        )
        return await self.db_session.scalar(query)

    async def get_published(
        self, char_sheet_id: int, number: int
    ) -> CharacterSheetVersion | None:
        """Fetch a sheet's published version by its per-sheet `number`."""
        query = (
            select(CharacterSheetVersion)
            .where(CharacterSheetVersion.character_sheet_id == char_sheet_id)
            .where(CharacterSheetVersion.number == number)
            .options(undefer(CharacterSheetVersion.layout))
        )
        return await self.db_session.scalar(query)

    async def get_version(self, version_id: int) -> CharacterSheetVersion | None:
        """Fetch a version by id, regardless of whether its sheet was deleted."""
        query = (
            select(CharacterSheetVersion)
            .where(CharacterSheetVersion.id == version_id)
            .options(undefer(CharacterSheetVersion.layout))
        )
        return await self.db_session.scalar(query)

    async def get_or_create_draft(
        self, char_sheet: CharacterSheet
    ) -> CharacterSheetVersion:
        """Return the sheet's draft, starting one from the latest published
        layout when there isn't one (publishing consumes the draft)."""
        draft = await self.get_draft(char_sheet.id)
        if draft is not None:
            return draft

        latest = await self.get_latest_published(char_sheet.id)
        draft = CharacterSheetVersion(
            character_sheet_id=char_sheet.id,
            schema_version=SCHEMA_VERSION,
            layout=copy.deepcopy(latest.layout)
            if latest is not None
            else mint_ids(default_sheet_layout()),
        )
        self.db_session.add(draft)
        await self.db_session.flush()

        return draft

    async def update_draft(
        self, version: CharacterSheetVersion, *, layout: dict
    ) -> CharacterSheetVersion:
        if not version.is_draft:
            raise ValueError("Published versions are immutable")

        version.layout = layout
        version.schema_version = SCHEMA_VERSION
        await self.db_session.flush()

        return version

    async def update_details(
        self, char_sheet: CharacterSheet, *, name: str, description: dict | None
    ) -> CharacterSheet:
        """Update the sheet-level (not versioned) name and description."""
        char_sheet.name = name
        char_sheet.description = description
        await self.db_session.flush()

        return char_sheet

    async def publish(
        self, version: CharacterSheetVersion, *, changelog: str | None = None
    ) -> CharacterSheetVersion:
        """Freeze a draft as the sheet's next numbered version."""
        if not version.is_draft:
            raise ValueError("Version is already published")

        latest_number = await self.db_session.scalar(
            select(func.max(CharacterSheetVersion.number)).where(
                CharacterSheetVersion.character_sheet_id == version.character_sheet_id
            )
        )
        version.number = (latest_number or 0) + 1
        version.changelog = changelog
        version.published_at = datetime.now(UTC)
        await self.db_session.flush()

        return version

    def _list_query(
        self,
        search: str | None = None,
        system_id: str | None = None,
        include_favorited: bool = False,
    ):
        ownership = CharacterSheet.creator_id == self.principal.id
        if include_favorited:
            favorited_public = and_(
                CharacterSheet.status.in_(
                    (CharacterSheet.Status.PUBLIC, CharacterSheet.Status.OFFICIAL)
                ),
                CharacterSheet.id.in_(
                    select(CharacterSheetFavorite.character_sheet_id).where(
                        CharacterSheetFavorite.user_id == self.principal.id
                    )
                ),
            )
            ownership = or_(ownership, favorited_public)
        query = select(CharacterSheet).where(ownership)
        if search:
            query = query.where(CharacterSheet.name.ilike(f"%{search}%"))
        if system_id:
            query = query.where(CharacterSheet.system_id == system_id)
        return query

    async def get_all(
        self,
        search: str | None = None,
        system_id: str | None = None,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
        include_favorited: bool = False,
    ) -> list[tuple[CharacterSheet, bool]]:
        query = (
            self._list_query(search, system_id, include_favorited)
            .add_columns(CharacterSheetFavorite.user_id.is_not(None).label("favorited"))
            .outerjoin(
                CharacterSheetFavorite,
                and_(
                    CharacterSheetFavorite.character_sheet_id == CharacterSheet.id,
                    CharacterSheetFavorite.user_id == self.principal.id,
                ),
            )
            .join(CharacterSheet.system)
            .order_by(System.sort_name.asc(), CharacterSheet.name.asc())
            .options(
                selectinload(CharacterSheet.creator),
                selectinload(CharacterSheet.system),
            )
            .limit(limit)
            .offset((page - 1) * limit)
        )
        result = await self.db_session.execute(query)
        return [(char_sheet, favorited) for char_sheet, favorited in result]

    async def count_all(
        self,
        search: str | None = None,
        system_id: str | None = None,
        include_favorited: bool = False,
    ) -> int:
        query = self._list_query(search, system_id, include_favorited)
        return (
            await self.db_session.scalar(
                select(func.count()).select_from(query.subquery())
            )
            or 0
        )

    def _library_query(
        self,
        search: str | None = None,
        system_ids: list[str] | None = None,
    ):
        query = (
            select(CharacterSheet)
            .where(
                CharacterSheet.status.in_(
                    (CharacterSheet.Status.PUBLIC, CharacterSheet.Status.OFFICIAL)
                )
            )
            .where(CharacterSheet.creator_id != self.principal.id)
        )
        if search:
            query = query.where(CharacterSheet.name.ilike(f"%{search}%"))
        if system_ids:
            query = query.where(CharacterSheet.system_id.in_(system_ids))
        return query

    async def get_library(
        self,
        search: str | None = None,
        system_ids: list[str] | None = None,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
    ) -> list[tuple[CharacterSheet, bool]]:
        query = (
            self._library_query(search, system_ids)
            .add_columns(CharacterSheetFavorite.user_id.is_not(None).label("favorited"))
            .outerjoin(
                CharacterSheetFavorite,
                and_(
                    CharacterSheetFavorite.character_sheet_id == CharacterSheet.id,
                    CharacterSheetFavorite.user_id == self.principal.id,
                ),
            )
            .join(CharacterSheet.system)
            .order_by(System.sort_name.asc(), CharacterSheet.name.asc())
            .options(
                selectinload(CharacterSheet.creator),
                selectinload(CharacterSheet.system),
            )
            .limit(limit)
            .offset((page - 1) * limit)
        )
        result = await self.db_session.execute(query)
        return [(char_sheet, favorited) for char_sheet, favorited in result]

    async def count_library(
        self,
        search: str | None = None,
        system_ids: list[str] | None = None,
    ) -> int:
        query = self._library_query(search, system_ids)
        return (
            await self.db_session.scalar(
                select(func.count()).select_from(query.subquery())
            )
            or 0
        )

    async def toggle_favorite(self, char_sheet: CharacterSheet) -> bool:
        existing = await self.db_session.get(
            CharacterSheetFavorite, (self.principal.id, char_sheet.id)
        )
        if existing:
            await self.db_session.delete(existing)
            await self.db_session.flush()
            return False

        self.db_session.add(
            CharacterSheetFavorite(
                user_id=self.principal.id, character_sheet_id=char_sheet.id
            )
        )
        await self.db_session.flush()
        return True

    async def delete(self, char_sheet: CharacterSheet) -> None:
        char_sheet.deleted = datetime.now(UTC)
        await self.db_session.execute(
            delete(CharacterSheetFavorite).where(
                CharacterSheetFavorite.character_sheet_id == char_sheet.id
            )
        )
        await self.db_session.flush()

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
            )
        )
        return await self.db_session.scalar(query)
