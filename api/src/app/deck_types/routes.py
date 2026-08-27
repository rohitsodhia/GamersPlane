from fastapi import APIRouter

from app.database import DBSessionDependency
from app.deck_types import schemas
from app.middleware import Principal
from app.repositories import (
    DeckRepository,
)

deck_types = APIRouter(prefix="/deck_types")


@deck_types.get("/", response_model=schemas.GetDeckTypesResponse)
async def get_deck_types(
    db_session: DBSessionDependency,
    principal: Principal,
):
    deck_repository = DeckRepository(db_session, principal=principal)
    deck_types = await deck_repository.get_deck_types()

    return schemas.GetDeckTypesResponse(
        types=[
            schemas.DeckTypeData(
                short=deck_type.short, name=deck_type.name, deck_size=deck_type.deck_size
            )
            for deck_type in deck_types
        ]
    )
