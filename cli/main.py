import asyncio
import json
from functools import wraps

import typer
from app.configs import configs
from app.database import session_manager
from app.repositories import ReferralLinkRepository
from mimesis import Text

app = typer.Typer()
mimesis_text = Text()


def async_command(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@app.callback()
def initialize():
    session_manager.init(
        host="localhost",
        port=configs.DATABASE_PORT,
        user=configs.DATABASE_USER,
        password=configs.DATABASE_PASSWORD,
        database=configs.DATABASE_DATABASE,
        dialect=configs.DATABASE_DIALECT,
    )


@app.command()
@async_command
async def seed():
    async with session_manager.transaction() as session:
        with open("data/referral_links.json") as f:
            referral_links_data = json.load(f)

        referral_links_repository = ReferralLinkRepository(session)
        for referral_link in referral_links_data:
            await referral_links_repository.add(**referral_link)


# @app.command()
# @async_command
# async def create_game():
#     async with session_manager.session() as session:
#         game_repository = GameRepository(session)
#         game = await game_repository.create_game(
#             title=" ".join(mimesis_text.words(3)),
#             system_id="custom",
#             gm_id=1,
#             post_frequency={"timesPer": random.randint(1, 5), "perPeriod": "d"},
#             num_players=random.randint(1, 6),
#             chars_per_player=1,
#             description=mimesis_text.sentence(),
#             char_gen_info=mimesis_text.sentence(),
#         )

#         print(f"Game {game.id} created: {game.title}")


if __name__ == "__main__":
    app()

    asyncio.run(session_manager.close())
