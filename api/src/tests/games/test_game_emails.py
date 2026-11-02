import pytest
from sqlalchemy import text

from app.configs import configs
from app.games import functions as game_functions
from app.models import Player, UserMeta
from app.repositories import GameRepository, PlayerRepository
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory
from tests.games.test_routes import _make_character, _put_in_game


class _GameEmailFixtures:
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
        forum = await create(ForumFactory, id=2, heritage=[])
        # Forcing an explicit id bypasses the "forums_id_seq" sequence, so any
        # later auto-generated forum id in this test could collide with it.
        await db_session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
                "(SELECT MAX(id) FROM forums))"
            )
        )
        return forum

    @pytest.fixture
    def sent(self, monkeypatch):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", True)
        calls = []

        async def fake_send_email(to, subject, content, **kwargs):
            calls.append({"to": to, "subject": subject, "content": content, **kwargs})

        monkeypatch.setattr(game_functions, "send_email", fake_send_email)
        return calls

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def game(self, db_session, gm, system):
        return await GameRepository(db_session, principal=gm).create(
            "My<br>Campaign",
            system.id,
            [system.id],
            gm.id,
            "3/w",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

    @pytest.fixture
    def add_player(self, db_session, create, game, gm):
        async def _add(state=Player.States.ACCEPTED, is_gm=False):
            user = await create(ActivatedUserFactory)
            await PlayerRepository(db_session, principal=gm).attach_player_to_game(
                game.id, user.id, is_gm=is_gm, state=state
            )
            return user

        return _add

    @pytest.fixture
    def set_pref(self, db_session):
        async def _set(user, key, value):
            db_session.add(UserMeta(user_id=user.id, key=key.value, value=value))
            await db_session.flush()

        return _set

    @staticmethod
    def recipients(sent):
        return sorted(call["to"] for call in sent)


class TestPlayerActsMailsGMs(_GameEmailFixtures):
    async def test_apply_mails_all_gms_by_default_but_not_opted_out(
        self, auth_as, client, create, game, gm, add_player, set_pref, sent
    ):
        co_gm = await add_player(is_gm=True)
        quiet_co_gm = await add_player(is_gm=True)
        await set_pref(quiet_co_gm, UserMeta.MetaKeys.GM_MAIL, False)
        applicant = await create(ActivatedUserFactory)
        client = auth_as(applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 204
        # No gmMail row for gm/co_gm counts as opted in.
        assert self.recipients(sent) == sorted([gm.email, co_gm.email])
        assert applicant.username in sent[0]["content"]
        assert sent[0]["subject"] == "[My Campaign] New application"

    async def test_primary_gm_can_opt_out_of_gm_mail(
        self, auth_as, client, create, game, gm, add_player, set_pref, sent
    ):
        co_gm = await add_player(is_gm=True)
        await set_pref(gm, UserMeta.MetaKeys.GM_MAIL, False)
        client = auth_as(await create(ActivatedUserFactory))

        await client.post(f"/games/{game.id}/apply")

        assert self.recipients(sent) == [co_gm.email]

    async def test_game_mail_off_does_not_silence_gm_mail(
        self, auth_as, client, create, game, gm, set_pref, sent
    ):
        # gameMail off only silences the player-facing mails.
        await set_pref(gm, UserMeta.MetaKeys.GAME_MAIL, False)
        client = auth_as(await create(ActivatedUserFactory))

        await client.post(f"/games/{game.id}/apply")

        assert self.recipients(sent) == [gm.email]

    async def test_email_disabled_sends_nothing(
        self, auth_as, client, create, game, sent, monkeypatch
    ):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", False)
        client = auth_as(await create(ActivatedUserFactory))

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 204
        assert sent == []

    @pytest.mark.parametrize(
        ("state", "subject"),
        [
            (Player.States.ACCEPTED, "A player left the game"),
            (Player.States.APPLIED, "Application withdrawn"),
            (Player.States.INVITED, "Invite declined"),
        ],
    )
    async def test_leaving_mails_gms_by_state(
        self, auth_as, client, game, gm, add_player, sent, state, subject
    ):
        player = await add_player(state=state)
        client = auth_as(player)

        response = await client.delete(f"/games/{game.id}/player/{player.id}")

        assert response.status_code == 204
        assert self.recipients(sent) == [gm.email]
        assert subject in sent[0]["subject"]

    async def test_co_gm_leaving_mails_other_gms_but_not_themselves(
        self, auth_as, client, game, gm, add_player, sent
    ):
        leaver = await add_player(is_gm=True)
        other_co_gm = await add_player(is_gm=True)
        client = auth_as(leaver)

        response = await client.delete(f"/games/{game.id}/player/{leaver.id}")

        assert response.status_code == 204
        assert self.recipients(sent) == sorted([gm.email, other_co_gm.email])
        assert "A GM left the game" in sent[0]["subject"]

    async def test_accept_invite_mails_gms(
        self, auth_as, client, game, gm, add_player, sent
    ):
        invitee = await add_player(state=Player.States.INVITED)
        client = auth_as(invitee)

        response = await client.post(f"/games/{game.id}/accept_invite")

        assert response.status_code == 204
        assert self.recipients(sent) == [gm.email]
        assert "Invite accepted" in sent[0]["subject"]

    async def test_player_submitting_character_mails_gms(
        self, auth_as, client, db_session, game, gm, add_player, sent
    ):
        player = await add_player()
        character = await _make_character(db_session, player, name="Strider")
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 204
        assert self.recipients(sent) == [gm.email]
        assert "Strider" in sent[0]["content"]

    async def test_gm_submitting_own_character_sends_nothing(
        self, auth_as, client, db_session, game, gm, add_player, sent
    ):
        co_gm = await add_player(is_gm=True)
        character = await _make_character(db_session, co_gm)
        client = auth_as(co_gm)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 204
        assert sent == []


class TestGMActsMailsPlayer(_GameEmailFixtures):
    async def test_invite_mails_invitee_only(
        self, auth_as, client, create, game, gm, add_player, sent
    ):
        invitee = await create(ActivatedUserFactory)
        await add_player(is_gm=True)
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert response.status_code == 204
        assert self.recipients(sent) == [invitee.email]
        assert sent[0]["subject"] == "[My Campaign] Game invite"
        assert f"{gm.username} has invited you to their" in sent[0]["content"]
        assert "/images/logos/dnd5e.png" in sent[0]["content"]

    async def test_email_disabled_sends_nothing_to_players(
        self, auth_as, client, game, gm, add_player, sent, monkeypatch
    ):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", False)
        applicant = await add_player(state=Player.States.APPLIED)
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{applicant.id}/approve")

        assert response.status_code == 204
        assert sent == []

    async def test_co_gm_approving_applicant_mails_only_the_applicant(
        self, auth_as, client, game, gm, add_player, sent
    ):
        co_gm = await add_player(is_gm=True)
        applicant = await add_player(state=Player.States.APPLIED)
        client = auth_as(co_gm)

        response = await client.post(f"/games/{game.id}/player/{applicant.id}/approve")

        assert response.status_code == 204
        assert self.recipients(sent) == [applicant.email]

    async def test_co_gm_approving_character_mails_only_the_owner(
        self, auth_as, client, db_session, game, gm, add_player, sent
    ):
        co_gm = await add_player(is_gm=True)
        player = await add_player()
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, game.id)
        client = auth_as(co_gm)

        response = await client.post(
            f"/games/{game.id}/characters/{character.id}/approve"
        )

        assert response.status_code == 204
        assert self.recipients(sent) == [player.email]

    async def test_game_mail_opt_out_blocks_player_mail(
        self, auth_as, client, create, game, gm, set_pref, sent
    ):
        invitee = await create(ActivatedUserFactory)
        await set_pref(invitee, UserMeta.MetaKeys.GAME_MAIL, False)
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert response.status_code == 204
        assert sent == []

    async def test_approve_player_mails_player_not_co_gms(
        self, auth_as, client, game, gm, add_player, sent
    ):
        await add_player(is_gm=True)
        applicant = await add_player(state=Player.States.APPLIED)
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{applicant.id}/approve")

        assert response.status_code == 204
        assert self.recipients(sent) == [applicant.email]
        assert "activity in your" in sent[0]["content"]

    @pytest.mark.parametrize(
        ("state", "subject"),
        [
            (Player.States.APPLIED, "Application declined"),
            (Player.States.ACCEPTED, "Removed from the game"),
            (Player.States.INVITED, "Invite withdrawn"),
        ],
    )
    async def test_gm_removing_player_mails_player_by_state(
        self, auth_as, client, game, gm, add_player, sent, state, subject
    ):
        target = await add_player(state=state)
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/player/{target.id}")

        assert response.status_code == 204
        assert self.recipients(sent) == [target.email]
        assert subject in sent[0]["subject"]
        assert "an update about the" in sent[0]["content"]

    async def test_gm_removing_co_gm_mails_the_removed_co_gm_only(
        self, auth_as, client, game, gm, add_player, sent
    ):
        co_gm = await add_player(is_gm=True)
        await add_player(is_gm=True)
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/player/{co_gm.id}")

        assert response.status_code == 204
        assert self.recipients(sent) == [co_gm.email]

    @pytest.mark.parametrize(
        ("start_as_gm", "subject"),
        [(False, "You're now a GM"), (True, "You're no longer a GM")],
    )
    async def test_toggle_gm_mails_the_affected_player_only(
        self, auth_as, client, game, gm, add_player, sent, start_as_gm, subject
    ):
        target = await add_player(is_gm=start_as_gm)
        await add_player(is_gm=True)
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{target.id}/toggle_gm")

        assert response.status_code == 204
        assert self.recipients(sent) == [target.email]
        assert subject in sent[0]["subject"]

    async def test_approve_character_mails_owner(
        self, auth_as, client, db_session, game, gm, add_player, sent
    ):
        player = await add_player()
        character = await _make_character(db_session, player, name="Strider")
        await _put_in_game(db_session, character, game.id)
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters/{character.id}/approve"
        )

        assert response.status_code == 204
        assert self.recipients(sent) == [player.email]
        assert sent[0]["subject"] == "[My Campaign] Character approved"

    async def test_approving_a_co_gms_character_sends_nothing(
        self, auth_as, client, db_session, game, gm, add_player, sent
    ):
        co_gm = await add_player(is_gm=True)
        character = await _make_character(db_session, co_gm)
        await _put_in_game(db_session, character, game.id)
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters/{character.id}/approve"
        )

        assert response.status_code == 204
        assert sent == []

    async def test_co_gm_approving_primary_gms_character_sends_nothing(
        self, auth_as, client, db_session, game, gm, add_player, sent
    ):
        co_gm = await add_player(is_gm=True)
        character = await _make_character(db_session, gm)
        await _put_in_game(db_session, character, game.id)
        client = auth_as(co_gm)

        response = await client.post(
            f"/games/{game.id}/characters/{character.id}/approve"
        )

        assert response.status_code == 204
        assert sent == []

    @pytest.mark.parametrize(
        ("approved", "subject"),
        [(False, "Character rejected"), (True, "Character removed")],
    )
    async def test_gm_removing_character_wording_follows_approval(
        self, auth_as, client, db_session, game, gm, add_player, sent, approved, subject
    ):
        player = await add_player()
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, game.id, approved=approved)
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/characters/{character.id}")

        assert response.status_code == 204
        assert self.recipients(sent) == [player.email]
        assert sent[0]["subject"] == f"[My Campaign] {subject}"

    async def test_owner_withdrawing_character_sends_nothing(
        self, auth_as, client, db_session, game, add_player, sent
    ):
        player = await add_player()
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, game.id, approved=True)
        client = auth_as(player)

        response = await client.delete(f"/games/{game.id}/characters/{character.id}")

        assert response.status_code == 204
        assert sent == []

    async def test_gm_removing_own_character_sends_nothing(
        self, auth_as, client, db_session, game, gm, sent
    ):
        character = await _make_character(db_session, gm)
        await _put_in_game(db_session, character, game.id, approved=True)
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/characters/{character.id}")

        assert response.status_code == 204
        assert sent == []
