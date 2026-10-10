"""The site-owned "Basic NPC" sheet GMs quick-make NPCs on.

The sheet lives at a fixed id (migrations reserve it by starting the
``character_sheets`` id sequence at 2) and its definition is the single source
of truth in ``seeds/basic_npc.json``, shared by the dev seed, the tests and the
production data migration. Field ids are hardcoded in the JSON (normally they're
server-minted) so the API can write the new NPC's ``name`` value by id.
"""

import json
from pathlib import Path

BASIC_NPC_SHEET_ID = 1

# The value-store id of the sheet's `name` field.
BASIC_NPC_NAME_FIELD_ID = "a3c91e07"

_SEED_PATH = Path(__file__).parent / "seeds" / "basic_npc.json"


def load_basic_npc_sheet() -> dict:
    """The sheet definition: ``name``, ``system_id``, ``status`` and ``layout``.
    Parsed fresh on each call so the caller may mutate it."""
    return json.loads(_SEED_PATH.read_text(encoding="utf-8"))
