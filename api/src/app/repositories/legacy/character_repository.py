from sqlalchemy import text

from app.database import DBSessionDependency
from app.models.legacy.user import User


class CharacterRepository:
    def __init__(self, db_session: DBSessionDependency, authed_user: User):
        self.db_session = db_session
        self.authed_user = authed_user

    async def get_header_characters(self):
        characters_result = await self.db_session.execute(
            text(
                "SELECT DISTINCT characters.characterID, characters.label, characters.system, IF(favorites.userID, 1, 0) isFavorite FROM characters LEFT JOIN characterLibrary_favorites favorites ON characters.characterID = favorites.characterID AND favorites.userID = :userID WHERE characters.userID = :userID AND characters.retired IS NULL ORDER BY isFavorite DESC, characters.label"
            ),
            {"userID": self.authed_user.id},
        )

        characters: list[dict] = []
        for character in characters_result:
            characters.append(
                {
                    "id": int(character[0]),
                    "label": character[1],
                    "system": character[2],
                    "isFavorite": bool(character[3]),
                }
            )

        return characters
