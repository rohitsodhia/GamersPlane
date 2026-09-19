import asyncio
import json
import random
from functools import wraps

import typer
from mimesis import Text
from sqlalchemy import text

from app.configs import configs
from app.database import session_manager
from app.models import (
    Character,
    DeckType,
    Forum,
    Player,
    Role,
    RolePermission,
    UserMeta,
)
from app.repositories import (
    CharacterRepository,
    CharacterSheetRepository,
    GameRepository,
    GenreRepository,
    PlayerRepository,
    PublisherRepository,
    ReferralLinkRepository,
    SystemRepository,
    UserRepository,
)
from app.users.functions import register_user


def prose(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


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
    async with session_manager.session() as session:
        with open("data/referral_links.json") as f:
            referral_links_data = json.load(f)
        referral_links_repository = ReferralLinkRepository(session)
        for referral_link in referral_links_data:
            await referral_links_repository.add(**referral_link)
        typer.echo("Referral links added")

        with open("data/publishers.json") as f:
            publishers_data = json.load(f)
        publisher_repo = PublisherRepository(session)
        for publisher in publishers_data:
            await publisher_repo.add(**publisher)
        typer.echo("Publishers added")

        publishers_by_name = {p.name: p for p in await publisher_repo.get_all()}
        with open("data/systems.json") as f:
            systems_data = json.load(f)
        genre_repo = GenreRepository(session)
        system_repo = SystemRepository(session)
        genres_by_name: dict = {}
        for system in systems_data:
            genre_objects = []
            for genre_name in system["genres"]:
                if genre_name not in genres_by_name:
                    genres_by_name[genre_name] = await genre_repo.add(genre_name)
                genre_objects.append(genres_by_name[genre_name])

            publisher = publishers_by_name[system["publisher"]]
            await system_repo.add(
                id=system["id"],
                name=system["name"],
                sort_name=system["sort_name"],
                publisher_id=publisher.id,
                genres=genre_objects,
                basics=system["basics"],
                has_char_sheet=system["has_char_sheet"],
                enabled=system["enabled"],
            )
        typer.echo("Systems added")

        primary_user = await register_user(
            session,
            email="contact@gamersplane.com",
            username="Keleth",
            password="test1234",
        )
        primary_user.activate()
        user_repo = UserRepository(session)
        await user_repo.update_user_meta(
            primary_user, {UserMeta.MetaKeys.AVATAR_EXT: "png"}
        )
        user = await register_user(
            session,
            email="test@test.com",
            username="Irdalth",
            password="test1234",
        )
        user.activate()
        user = await register_user(
            session,
            email="test2@test.com",
            username="Soliin",
            password="test1234",
        )
        user.activate()
        typer.echo("Users added")

        admin_role = Role(name="Administrator", owner=primary_user)
        admin_role.grant(RolePermission.ValidPermissions.ADMIN)
        admin_role.users.append(primary_user)
        session.add(admin_role)
        typer.echo("Admin role added")

        with open("data/forums.json") as f:
            forums_data = json.load(f)
        for forum_data in forums_data:
            session.add(Forum(**forum_data))
        await session.flush()
        await session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
                "(SELECT MAX(id) FROM forums))"
            )
        )
        typer.echo("Forums added")

        with open("data/deck_types.json") as f:
            deck_types_data = json.load(f)
        for deck_type_data in deck_types_data:
            session.add(DeckType(**deck_type_data))
        typer.echo("Deck Types added")

        character_sheet_repo = CharacterSheetRepository(session, primary_user)
        await character_sheet_repo.create(
            name="Test 1",
            system_id="dnd5",
        )
        typer.echo("Character Sheet added")

        character_repo = CharacterRepository(session, primary_user)
        character = await character_repo.create(
            label="Test 1",
            type=Character.Type.PC,
            character_sheet_id=1,
        )
        character.values = {
            "notes": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "attrs": {"textAlign": None},
                        "content": [
                            {
                                "type": "text",
                                "marks": [{"type": "bold"}],
                                "text": "aweva",
                            }
                        ],
                    }
                ],
            },
            "name": "Test",
        }
        typer.echo("Character added")


@app.command()
@async_command
async def create_user(
    username: str = typer.Option(..., prompt=True),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, confirmation_prompt=True
    ),
    activate: bool = typer.Option(True),
):
    async with session_manager.session() as session:
        user = await register_user(
            session, email=email, username=username, password=password
        )
        if activate:
            user.activate()


@app.command()
@async_command
async def create_game(
    system_id: str = typer.Option("custom", prompt=True),
    allowed_char_sheets: str = typer.Option(
        "custom", prompt="Allowed char sheets (comma separated)"
    ),
    gm_id: int = typer.Option(1, prompt="GM Id"),
):
    allowed_char_sheets_list = [
        s.strip() for s in allowed_char_sheets.split(",") if s.strip()
    ]

    async with session_manager.session() as session:
        user_repository = UserRepository(session)
        gm = await user_repository.get_user(gm_id)
        if gm is None:
            typer.echo(f"No user with id {gm_id}")
            raise typer.Exit(code=1)

        game_repository = GameRepository(session, principal=gm)
        game = await game_repository.create(
            title=" ".join(mimesis_text.words(3)),
            system_id=system_id,
            allowed_char_sheets=allowed_char_sheets_list,
            gm_id=gm_id,
            post_frequency=f"{random.randint(1, 5)}/d",
            num_players=random.randint(1, 6),
            chars_per_player=1,
            description=prose(mimesis_text.sentence()),
            char_gen_info=prose(mimesis_text.sentence()),
            public=True,
            recruitment_thread_id=None,
            advanced_options=None,
        )
        player_repository = PlayerRepository(session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, gm_id, is_gm=True, state=Player.States.ACCEPTED
        )

        typer.echo(f"Game {game.id} created: {game.title}")


if __name__ == "__main__":
    app()

    asyncio.run(session_manager.close())
