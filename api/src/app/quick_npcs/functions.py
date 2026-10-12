from app.configs import configs
from app.games.npc_schemas import GameImageData, NPCData
from app.models import GameImage, GameNPC


def game_image_url(image: GameImage) -> str:
    return f"{configs.AVATARS_ROOT}/npcs/{image.id}.{image.ext}"


def build_image_data(image: GameImage) -> GameImageData:
    return GameImageData(id=image.id, url=game_image_url(image))


def build_npc_data(npc: GameNPC) -> NPCData:
    return NPCData(
        id=npc.id,
        name=npc.name,
        image=build_image_data(npc.image) if npc.image is not None else None,
        last_used_at=npc.last_used_at,
    )
