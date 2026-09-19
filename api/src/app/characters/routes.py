from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.characters import schemas
from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.helpers.avatars import process_avatar_upload, save_avatar
from app.middleware import Principal
from app.models import Character
from app.repositories import CharacterRepository, CharacterSheetRepository

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

    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.create(
        character_sheet_id=data.character_sheet_id,
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
    system_id: str | None = None,
    page: int = 1,
):
    if page < 1:
        page = 1

    character_repository = CharacterRepository(db_session, principal)
    characters = await character_repository.get_all(
        search=search, type=type, system_id=system_id, page=page
    )
    total = await character_repository.count_all(
        search=search, type=type, system_id=system_id
    )

    return schemas.GetCharactersResponse(
        characters=[_character_response(character) for character in characters],
        total=total,
        page=page,
    )


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
    if not character.in_library and character.user_id != principal.id:
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
            layout=sheet.layout,
        ),
        avatars=[_avatar_data(avatar) for avatar in character.avatars],
    )
