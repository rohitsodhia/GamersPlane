from __future__ import annotations

from app.schema_base import SchemaBase, filtered_str


class CreateCharSheetInput(SchemaBase):
    label: str = filtered_str()
    system_id: str


class CreateCharSheetResponse(SchemaBase):
    id: int
