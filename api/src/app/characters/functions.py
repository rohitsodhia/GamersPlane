from app.models import Character, User


def can_view_character(
    character: Character, principal: User | None, is_game_gm: bool
) -> bool:
    """Whether the principal (None when logged out) may open the character.

    Besides the owner, a library character is open to anyone, and one submitted
    to a game is open to that game's GMs. ``is_game_gm`` is whether the principal
    GMs the character's game, passed in so callers that already know it (or are
    checking many characters of one game) don't query per character.
    """
    return (
        character.in_library
        or (principal is not None and character.user_id == principal.id)
        or (character.game_id is not None and is_game_gm)
    )
