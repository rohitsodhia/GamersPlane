import copy
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.character_sheets.defaults import default_sheet_layout
from app.character_sheets.layout_ids import IdDiff, mint_ids, validate_publish_ids
from app.character_sheets.layout_validation import (
    SCHEMA_VERSION,
    validate_publishable_layout,
)
from app.configs import configs
from app.exceptions import ConflictException
from app.models import (
    CharacterSheet,
    CharacterSheetFavorite,
    CharacterSheetVersion,
    System,
    User,
)


def _minted(layout: dict) -> dict:
    """A copy of `layout` with its field ids minted, so the caller's dict is
    never mutated."""
    return mint_ids(copy.deepcopy(layout))


class CharacterSheetRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def create(
        self, name: str, system_id: str, layout: dict | None = None
    ) -> CharacterSheet:
        """Create a sheet with its initial draft version, minting field ids on
        `layout` (or the default layout when none is given)."""
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
                layout=_minted(
                    layout if layout is not None else default_sheet_layout()
                ),
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

    async def update_draft(
        self, version: CharacterSheetVersion, *, layout: dict
    ) -> CharacterSheetVersion:
        if not version.is_draft:
            raise ValueError("Published versions are immutable")

        version.layout = _minted(layout)
        version.schema_version = SCHEMA_VERSION
        await self.db_session.flush()

        return version

    async def save_draft(
        self, char_sheet: CharacterSheet, *, layout: dict
    ) -> CharacterSheetVersion:
        """Save `layout` as the sheet's draft and return the version now
        holding it.

        A save that doesn't change anything is a no-op: with no draft open and
        `layout` identical to the latest published version, no draft is
        started and that published version is returned instead.
        """
        draft = await self.get_draft(char_sheet.id)
        if draft is not None:
            return await self.update_draft(draft, layout=layout)

        layout = _minted(layout)
        latest = await self.get_latest_published(char_sheet.id)
        if latest is not None and latest.layout == layout:
            return latest

        draft = CharacterSheetVersion(
            character_sheet_id=char_sheet.id,
            schema_version=SCHEMA_VERSION,
            layout=layout,
        )
        self.db_session.add(draft)
        await self.db_session.flush()

        return draft

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

    async def publish_draft(
        self, char_sheet: CharacterSheet, *, changelog: str | None = None
    ) -> tuple[CharacterSheetVersion, IdDiff]:
        """Validate the sheet's draft and publish it as the next version.

        The gated counterpart to :meth:`publish` -- the path the API and CLI
        use. Returns the new version plus the field ids it added/removed
        relative to the previously published one.

        A draft identical to the latest published version (e.g. edits that
        were reverted) publishes nothing: the draft is discarded and the
        latest published version is returned with an empty diff.
        """
        draft = await self.get_draft(char_sheet.id)
        if draft is None:
            raise ConflictException("There are no unpublished changes to publish")

        previous = await self.get_latest_published(char_sheet.id)
        if previous is not None and draft.layout == previous.layout:
            await self.db_session.delete(draft)
            await self.db_session.flush()
            return previous, IdDiff(added=[], removed=[])

        validate_publishable_layout(draft.layout)
        id_diff = validate_publish_ids(
            previous.layout if previous is not None else None, draft.layout
        )

        return await self.publish(draft, changelog=changelog), id_diff

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
