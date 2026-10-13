from pathlib import Path

from app.configs import configs
from app.exceptions import NotFoundException, ValidationError
from app.helpers.avatars import process_avatar_upload, save_avatar
from app.models import NPCImage, QuickNPC, User
from app.quick_npcs.schemas import NPCData, NPCImageData, UpdateNPCInput
from app.repositories import NPCOwner, QuickNPCRepository


def npc_image_url(image: NPCImage) -> str:
    return f"{configs.AVATARS_ROOT}/npcs/{image.id}.{image.ext}"


def build_image_data(image: NPCImage) -> NPCImageData:
    return NPCImageData(id=image.id, url=npc_image_url(image))


def can_edit_npc(npc: QuickNPC, principal: User, is_gm: bool) -> bool:
    """Personal NPCs can't be edited by anyone (there is no management UI for the
    personal library); a game's pairs are for its GMs and whoever made them."""
    if npc.user_id is not None:
        return False
    return is_gm or npc.created_by == principal.id


def build_npc_data(npc: QuickNPC, principal: User, is_gm: bool = False) -> NPCData:
    return NPCData(
        id=npc.id,
        name=npc.name,
        image=build_image_data(npc.image) if npc.image is not None else None,
        last_used_at=npc.last_used_at,
        can_edit=can_edit_npc(npc, principal, is_gm),
    )


async def get_npc_or_404(
    npc_repository: QuickNPCRepository, owner: NPCOwner, npc_id: int
) -> QuickNPC:
    npc = await npc_repository.get_npc(npc_id)
    if not npc or not owner.owns(npc):
        raise NotFoundException("NPC not found")
    return npc


async def require_npc_image(
    npc_repository: QuickNPCRepository, owner: NPCOwner, image_id: int
) -> NPCImage:
    """An image from the owner's library, as named in a request body."""
    image = await npc_repository.get_image(image_id)
    if not image or not owner.owns(image):
        raise ValidationError(
            "That image isn't in this game's library"
            if owner.game_id is not None
            else "That image isn't in your library"
        )
    return image


async def store_npc_image(
    npc_repository: QuickNPCRepository, owner: NPCOwner, contents: bytes
) -> NPCImageData:
    """Process an uploaded image and add it to the owner's library."""
    image, ext = process_avatar_upload(contents)
    npc_image = await npc_repository.create_image(owner, ext)
    save_avatar(image, Path(configs.AVATARS_DIR + "/npcs") / f"{npc_image.id}.{ext}")
    return build_image_data(npc_image)


async def update_npc(
    npc_repository: QuickNPCRepository,
    owner: NPCOwner,
    npc: QuickNPC,
    data: UpdateNPCInput,
) -> QuickNPC:
    """Apply a PATCH: an absent field is left alone, a null ``image_id`` drops
    the image."""
    if "name" in data.model_fields_set and data.name is None:
        raise ValidationError("An NPC needs a name")
    name = data.name if data.name is not None else npc.name
    image = npc.image
    if "image_id" in data.model_fields_set:
        image = (
            await require_npc_image(npc_repository, owner, data.image_id)
            if data.image_id is not None
            else None
        )
    return await npc_repository.update(npc, name, image)
