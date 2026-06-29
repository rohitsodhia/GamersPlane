from sqlalchemy import func, select, text

from app.database import DBSessionDependency
from app.models.legacy import Forum, Game, Player, User
from app.repositories.legacy import ForumRepository


class GameRepository:
    def __init__(
        self, db_session: DBSessionDependency, authed_user: User | None = None
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    async def create_game(
        self,
        *_,
        title: str,
        system_id: str,
        allowed_char_sheets: list[str] = [],
        gm_id: int,
        post_frequency: Game.PostFrequency,
        num_players: int,
        chars_per_player: int,
        description: str = "",
        char_gen_info: str = "",
    ):
        forum_repository = ForumRepository(self.db_session)
        forum_count = (
            await self.db_session.scalar(
                select(func.count()).select_from(Forum).where(Forum.parent_id == 2)
            )
            or 0
        )
        forum = await forum_repository.create_forum(
            title=title,
            forum_type=Forum.ForumTypes.FORUM,
            parent_id=2,
            order=forum_count + 1,
        )
        forum_group = await forum_repository.create_forum_group(
            name=title, owner_id=gm_id
        )

        game = Game(
            title=title,
            system_id=system_id,
            gm_id=gm_id,
            post_frequency=post_frequency,
            num_players=num_players,
            chars_per_player=chars_per_player,
            description=description,
            char_gen_info=char_gen_info,
            root_forum=forum,
            group=forum_group,
            public=True,
            allowed_char_sheets=allowed_char_sheets,
        )
        self.db_session.add(game)
        forum.game_id = game.id

        player = Player(game=game, user_id=gm_id)
        self.db_session.add(player)

        return game

    async def get_header_games(self):
        games_result = await self.db_session.execute(
            text(
                "SELECT games.gameID, games.title, games.forumID, games.retired, IF(players.isGM, players.isGM, FALSE) isGM, IF(players.userID, TRUE, FALSE) isPlayer, IF(favorites.userID, 1, 0) isFavorite FROM games LEFT JOIN players ON games.gameID = players.gameID AND players.userID = :userID LEFT JOIN games_favorites favorites ON games.gameID = favorites.gameID AND favorites.userID = :userID WHERE (players.userID IS NOT NULL OR favorites.userID IS NOT NULL) ORDER BY isFavorite DESC, isGM DESC, isPlayer DESC, games.title"
            ),
            {"userID": self.authed_user.id},
        )

        games: list[dict] = []
        for game in games_result:
            games.append(
                {
                    "gameID": int(game[0]),
                    "title": game[1],
                    "forumID": int(game[2]),
                    "retired": bool(game[3]),
                    "isGM": bool(game[4]),
                    "isPlayer": bool(game[5]),
                    "isFavorite": bool(game[6]),
                }
            )

        return games
