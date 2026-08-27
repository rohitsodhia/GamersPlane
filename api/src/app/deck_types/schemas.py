from __future__ import annotations

from app.schema_base import SchemaBase


class DeckTypeData(SchemaBase):
    short: str
    name: str
    deck_size: int


class GetDeckTypesResponse(SchemaBase):
    types: list[DeckTypeData]
