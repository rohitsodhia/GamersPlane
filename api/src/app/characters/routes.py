from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.character_sheets.character_values import hidden_values
from app.characters import schemas
from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationError,
)
from app.helpers.avatars import process_avatar_upload, save_avatar
from app.middleware import Principal
from app.models import Character, CharacterSheet, CharacterSheetVersion
from app.repositories import (
    CharacterRepository,
    CharacterSheetRepository,
    PlayerRepository,
)

characters = APIRouter(prefix="/characters")

AVATAR_MAX_COUNT = 5


@characters.post("/", response_model=schemas.CreateCharacterResponse)
async def create_character(
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.CreateCharacterInput,
):
    sheet_repository = CharacterSheetRepository(db_session, principal)
    sheet = await sheet_repository.get(data.character_sheet_id)
    if sheet is None:
        raise NotFoundException("Character sheet not found")
    if not sheet.is_public and sheet.creator_id != principal.id:
        raise ForbiddenException("Character sheet not available")

    version = await sheet_repository.get_latest_published(sheet.id)
    if version is None:
        raise ConflictException("Character sheet has not been published")

    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.create(
        character_sheet_id=data.character_sheet_id,
        character_sheet_version_id=version.id,
        label=data.label,
        type=data.type,
    )

    return schemas.CreateCharacterResponse(id=character.id)


@characters.get("", response_model=schemas.GetCharactersResponse)
async def get_characters(
    db_session: DBSessionDependency,
    principal: Principal,
    search: str | None = None,
    type: Character.Type | None = None,
    systems: list[str] = Query([]),
    in_game: bool | None = None,
    page: int = 1,
):
    if page < 1:
        page = 1

    character_repository = CharacterRepository(db_session, principal)
    characters = await character_repository.get_all(
        search=search,
        type=type,
        system_ids=systems,
        in_game=in_game,
        page=page,
        include_favorited=True,
    )
    total = await character_repository.count_all(
        search=search,
        type=type,
        system_ids=systems,
        in_game=in_game,
        include_favorited=True,
    )

    return schemas.GetCharactersResponse(
        characters=[
            schemas.CharacterListItem(
                id=character.id,
                label=character.label,
                type=character.type,
                in_library=character.in_library,
                user=schemas.LibraryUserData(
                    id=character.user.id, username=character.user.username
                ),
                character_sheet_id=character.character_sheet_id,
                character_sheet=schemas.CharacterListSheetData(
                    id=character.character_sheet.id,
                    name=character.character_sheet.name,
                    system=schemas.SystemData(
                        id=character.character_sheet.system.id,
                        name=character.character_sheet.system.name,
                    ),
                ),
                sheet_deleted=character.character_sheet.deleted is not None,
            )
            for character in characters
        ],
        total=total,
        page=page,
    )


@characters.get("/library", response_model=schemas.GetLibraryResponse)
async def get_library(
    db_session: DBSessionDependency,
    principal: Principal,
    search: str | None = None,
    type: Character.Type | None = None,
    systems: list[str] = Query([]),
    page: int = 1,
):
    if page < 1:
        page = 1

    character_repository = CharacterRepository(db_session, principal)
    characters = await character_repository.get_library(
        search=search, type=type, system_ids=systems, page=page
    )
    total = await character_repository.count_library(
        search=search, type=type, system_ids=systems
    )

    return schemas.GetLibraryResponse(
        characters=[
            schemas.LibraryCharacterData(
                id=character.id,
                label=character.label,
                system=schemas.SystemData(
                    id=character.character_sheet.system.id,
                    name=character.character_sheet.system.name,
                ),
                user=schemas.LibraryUserData(
                    id=character.user.id, username=character.user.username
                ),
                favorited=favorited,
            )
            for character, favorited in characters
        ],
        total=total,
        page=page,
    )


@characters.post("/sheet_moves", status_code=status.HTTP_204_NO_CONTENT)
async def move_characters_sheet(
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.MoveSheetInput,
):
    """Move characters to another sheet version: upgrading (a newer version of
    the same sheet) or changing (a version of a copy of it). All of them move,
    or none do."""
    character_repository = CharacterRepository(db_session, principal)
    sheet_repository = CharacterSheetRepository(db_session, principal)

    character_ids = set(data.character_ids)
    moving = await character_repository.get_many(list(character_ids))
    if len(moving) != len(character_ids):
        raise NotFoundException("Character not found")
    for character in moving:
        if character.user_id != principal.id:
            raise ForbiddenException("Character not available")

    targets = [
        await _move_target(
            sheet_repository, character, data.character_sheet_id, data.version
        )
        for character in moving
    ]
    for character, (char_sheet, version) in zip(moving, targets, strict=True):
        await character_repository.move_sheet(character, char_sheet, version)


@characters.get("/{character_id}", response_model=schemas.GetCharacterResponse)
async def get_character(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    # Besides the owner, a library character is open to anyone, and one
    # submitted to a game is open to that game's GMs.
    if (
        not character.in_library
        and character.user_id != principal.id
        and not (
            character.game_id is not None
            and await PlayerRepository(db_session, principal).is_gm(
                character.game_id, principal.id
            )
        )
    ):
        raise ForbiddenException("Character not available")

    return _character_response(character)


@characters.patch("/{character_id}", response_model=schemas.GetCharacterResponse)
async def update_character(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.UpdateCharacterInput,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    await character_repository.update(
        character, label=data.label, type=data.type, values=data.values
    )

    return _character_response(character)


@characters.get(
    "/{character_id}/sheet_moves", response_model=schemas.GetSheetMovesResponse
)
async def get_character_sheet_moves(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Where the character can move: newer versions of its sheet (upgrades)
    and copies of its sheet (changes)."""
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    sheet_repository = CharacterSheetRepository(db_session, principal)
    current_sheet = character.character_sheet
    versions = []
    if current_sheet.deleted is None and (
        current_sheet.is_public or current_sheet.creator_id == principal.id
    ):
        versions = await sheet_repository.get_published_versions(
            current_sheet.id, newer_than=character.character_sheet_version.number
        )
    copies = await sheet_repository.get_copies(current_sheet.id)

    return schemas.GetSheetMovesResponse(
        versions=[
            schemas.SheetMoveVersionData(
                number=version.number,
                published_at=version.published_at,
                changelog=version.changelog,
            )
            for version in versions
        ],
        copies=[
            schemas.SheetMoveCopyData(
                id=char_sheet.id,
                name=char_sheet.name,
                creator=schemas.LibraryUserData(
                    id=char_sheet.creator.id, username=char_sheet.creator.username
                ),
                latest_version_number=latest_number,
            )
            for char_sheet, latest_number in copies
        ],
    )


@characters.get(
    "/{character_id}/sheet_moves/preview",
    response_model=schemas.GetSheetMovePreviewResponse,
)
async def preview_character_sheet_move(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    character_sheet_id: int,
    version: int,
):
    """The layout the character would move to, and which of its values that
    layout won't show."""
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    sheet_repository = CharacterSheetRepository(db_session, principal)
    char_sheet, target = await _move_target(
        sheet_repository, character, character_sheet_id, version
    )

    return schemas.GetSheetMovePreviewResponse(
        name=char_sheet.name,
        layout=target.layout,
        hidden_values=[
            schemas.HiddenValueData(id=field_id, label=label)
            for field_id, label in hidden_values(
                character.values,
                character.character_sheet_version.layout,
                target.layout,
            )
        ],
    )


@characters.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    await character_repository.delete(character)


@characters.patch(
    "/{character_id}/toggle_library", status_code=status.HTTP_204_NO_CONTENT
)
async def toggle_character_library(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    await character_repository.toggle_library(character)


@characters.patch(
    "/{character_id}/toggle_favorite",
    response_model=schemas.ToggleCharacterFavoriteResponse,
)
async def toggle_character_favorite(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if not character.in_library and character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    favorited = await character_repository.toggle_favorite(character)

    return schemas.ToggleCharacterFavoriteResponse(favorited=favorited)


@characters.post(
    "/{character_id}/avatar",
    response_model=schemas.UpdateCharacterAvatarResponse,
)
async def add_character_avatar(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    avatar: UploadFile = File(...),
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")
    if len(character.avatars) >= AVATAR_MAX_COUNT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A character can have at most {AVATAR_MAX_COUNT} avatars",
        )

    contents = await avatar.read()
    image, ext = process_avatar_upload(contents)

    new_avatar = await character_repository.add_avatar(character, ext)

    avatars_dir = Path(configs.AVATARS_DIR + "/characters")
    save_avatar(image, avatars_dir / f"{new_avatar.id}.{ext}")

    return {"success": True, "avatar": _avatar_data(new_avatar)}


@characters.delete(
    "/{character_id}/avatar/{avatar_id}",
    response_model=schemas.DeleteCharacterAvatarResponse,
)
async def delete_character_avatar(
    character_id: int,
    avatar_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    deleted_avatar = await character_repository.delete_avatar(character, avatar_id)
    if deleted_avatar is None:
        raise NotFoundException("Avatar not found")

    avatars_dir = Path(configs.AVATARS_DIR + "/characters")
    (avatars_dir / f"{deleted_avatar.id}.{deleted_avatar.ext}").unlink(missing_ok=True)

    return {"success": True}


@characters.patch(
    "/{character_id}/avatar/{avatar_id}",
    response_model=schemas.SetPrimaryCharacterAvatarResponse,
)
async def set_primary_character_avatar(
    character_id: int,
    avatar_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")

    avatar = await character_repository.set_primary_avatar(character, avatar_id)
    if avatar is None:
        raise NotFoundException("Avatar not found")

    return {"success": True, "avatar": _avatar_data(avatar)}


async def _move_target(
    sheet_repository: CharacterSheetRepository,
    character: Character,
    char_sheet_id: int,
    version_number: int,
) -> tuple[CharacterSheet, CharacterSheetVersion]:
    """The sheet and version `character` would move to. Moves only go forward:
    to a newer version of the character's own sheet, or to any version of a
    copy of it. Deleted sheets are never a target."""
    char_sheet = await sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")
    if (
        not char_sheet.is_public
        and char_sheet.creator_id != sheet_repository.principal.id
    ):
        raise ForbiddenException("Character sheet not available")

    if char_sheet.id == character.character_sheet_id:
        if version_number <= character.character_sheet_version.number:
            raise ValidationError(
                f"'{character.label}' can only upgrade to a newer version"
            )
    elif not await sheet_repository.is_copy_of(
        char_sheet.id, character.character_sheet_id
    ):
        raise ValidationError(
            f"'{character.label}' can only change to a copy of its sheet"
        )

    version = await sheet_repository.get_published(char_sheet.id, version_number)
    if version is None:
        raise NotFoundException("Character sheet version not found")

    return char_sheet, version


def _avatar_data(avatar) -> schemas.CharacterAvatarData:
    return schemas.CharacterAvatarData(
        id=avatar.id,
        url=f"{configs.AVATARS_ROOT}/characters/{avatar.id}.{avatar.ext}",
        is_primary=avatar.is_primary,
    )


def _character_response(character) -> schemas.GetCharacterResponse:
    sheet = character.character_sheet

    return schemas.GetCharacterResponse(
        id=character.id,
        user_id=character.user_id,
        label=character.label,
        name=character.name,
        type=character.type,
        values=character.values,
        in_library=character.in_library,
        character_sheet_id=character.character_sheet_id,
        character_sheet=schemas.CharacterSheetData(
            id=sheet.id,
            name=sheet.name,
            creator=schemas.UserData(
                id=sheet.creator.id,
                username=sheet.creator.username,
                avatar=sheet.creator.avatar,
            ),
            system=schemas.SystemData(
                id=sheet.system.id,
                name=sheet.system.name,
            ),
        ),
        sheet_deleted=sheet.deleted is not None,
        version_id=character.character_sheet_version.id,
        version_number=character.character_sheet_version.number,
        layout=character.character_sheet_version.layout,
        avatars=[_avatar_data(avatar) for avatar in character.avatars],
    )
