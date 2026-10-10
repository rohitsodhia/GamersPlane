"""Shared setup for tests that need a real game with a forum and a deck."""

from dataclasses import dataclass

from sqlalchemy import text

from app.models import Deck, DeckPermission, Forum, Game, Player, RolePermission, User
from app.repositories import DeckRepository, GameRepository, PlayerRepository
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    DeckTypeFactory,
    ForumFactory,
    RoleFactory,
    SystemFactory,
)

Verbs = RolePermission.ValidPermissions

PLAYER_VERBS = (
    Verbs.FORUM_READ,
    Verbs.FORUM_WRITE,
    Verbs.FORUM_EDIT,
    Verbs.FORUM_CREATE_THREAD,
    Verbs.FORUM_ADD_ROLLS,
    Verbs.FORUM_ADD_DRAWS,
)


@dataclass
class GameForum:
    gm: User
    game: Game
    forum: Forum
    deck: Deck
    make_game: object


async def grant(db_session, user, forum, *verbs):
    """Give ``user`` a role holding ``verbs`` on ``forum``."""
    role = RoleFactory.build()
    db_session.add(role)
    for verb in verbs:
        role.grant(verb, scope_type=RolePermission.ScopeTypes.FORUM, scope_id=forum.id)
    role.users.append(user)
    await db_session.flush()


async def allow_drawing(db_session, user, deck):
    db_session.add(DeckPermission(user_id=user.id, deck_id=deck.id))
    await db_session.flush()


async def make_user_with(create, db_session, forum, *verbs):
    user = await create(ActivatedUserFactory)
    await grant(db_session, user, forum, *verbs)
    return user


async def make_game_forum(create, db_session) -> GameForum:
    """A game (GM attached as a player) with its forum and one 52-card deck.

    ``make_game`` builds another game the same way, for cross-game checks.
    """
    await create(ForumFactory, id=GAMES_ROOT_FORUM_ID, heritage=[])
    # An explicit id bypasses the forums sequence, so move it past that id.
    await db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
            "(SELECT MAX(id) FROM forums))"
        )
    )
    system = await create(SystemFactory, id="dnd5e")
    deck_type = await create(DeckTypeFactory, deck_size=52)

    async def make_game(title: str = "My Campaign"):
        gm = await create(ActivatedUserFactory)
        game = await GameRepository(db_session, principal=gm).create(
            title, system.id, [], gm.id, "3/w", 4, 1, None, None, True, None, None
        )
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        forum = await db_session.get(Forum, game.root_forum_id)
        deck = await DeckRepository(db_session, principal=gm).create(
            game_id=game.id, label="Fate Deck", type=deck_type.short, permissions=[]
        )
        return GameForum(gm, game, forum, deck, make_game)

    return await make_game()
