from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.models import Post, RolePermission
from app.repositories import ThreadRepository
from app.threads.routes import ANNOUNCEMENTS_FORUM_ID
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ForumFactory,
    PostFactory,
    ThreadFactory,
    UserFactory,
    prose_doc,
)
from tests.game_forum import PLAYER_VERBS, make_game_forum, make_user_with

Verbs = RolePermission.ValidPermissions

SECRET = "the secret plan"


def para(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def note(*user_ids, text=SECRET, mode=None, **extra_attrs):
    attrs = {"userIds": list(user_ids), **extra_attrs}
    if mode is not None:
        attrs["mode"] = mode
    return {"type": "note", "attrs": attrs, "content": [para(text)]}


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def thread(create, world):
    return await create(ThreadFactory, forum=world.forum)


@pytest.fixture
async def author(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


@pytest.fixture
async def recipient(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


@pytest.fixture
async def other(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


@pytest.fixture
async def moderator(create, db_session, world):
    return await make_user_with(
        create, db_session, world.forum, *PLAYER_VERBS, Verbs.FORUM_MODERATE
    )


@pytest.fixture
async def noted_post(create, thread, author, recipient):
    """A post by ``author`` holding a note for ``recipient`` and a private one."""
    body = doc(
        para("public words"),
        note(recipient.id, text=SECRET),
        note(recipient.id, text="private words", mode="private"),
    )
    return await create(PostFactory, thread=thread, author=author, body=body)


def reads_all(response):
    return SECRET in response.text and "private words" in response.text


class TestGetPostsRedaction:
    @pytest.mark.parametrize("viewer", ["author", "gm", "moderator"])
    async def test_those_who_may_read_notes_get_the_full_body(
        self, auth_as, thread, noted_post, world, author, moderator, viewer
    ):
        user = {"author": author, "gm": world.gm}.get(viewer, moderator)
        client = auth_as(user)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert reads_all(response)

    async def test_another_user_gets_a_stub_and_no_private_note(
        self, auth_as, thread, noted_post, other, recipient
    ):
        client = auth_as(other)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert SECRET not in response.text
        assert "private words" not in response.text
        body = response.json()["posts"][0]
        assert "public words" in response.text
        notes = [n for n in body["body"]["content"] if n["type"] == "note"]
        assert len(notes) == 1
        assert notes[0]["attrs"] == {
            "mode": "note",
            "userIds": [recipient.id],
            "hidden": True,
        }
        # The stub's names come from the response, not from the body.
        assert body["note_recipients"] == [
            {"id": recipient.id, "username": recipient.username}
        ]

    async def test_a_guest_reading_a_public_thread_gets_a_stub(self, client, create):
        thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread, body=doc(note(1), para("hello")))

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.status_code == 200
        assert SECRET not in response.text
        notes = [
            n
            for n in response.json()["posts"][0]["body"]["content"]
            if n["type"] == "note"
        ]
        assert [n["attrs"]["hidden"] for n in notes] == [True]

    async def test_a_mention_inside_a_hidden_note_is_not_listed(
        self, auth_as, create, thread, author, other, recipient
    ):
        mention = {"type": "mention", "attrs": {"userId": recipient.id}}
        body = doc(
            {
                "type": "note",
                "attrs": {"userIds": []},
                "content": [{"type": "paragraph", "content": [mention]}],
            }
        )
        await create(PostFactory, thread=thread, author=author, body=body)
        client = auth_as(other)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["content_mentions"] == []

    async def test_a_deleted_recipient_is_left_out_of_the_names(
        self, auth_as, create, thread, author, other
    ):
        await create(PostFactory, thread=thread, author=author, body=doc(note(987654)))
        client = auth_as(other)

        response = await client.get("/posts", params={"thread_id": thread.id})

        post = response.json()["posts"][0]
        assert post["note_recipients"] == []
        assert post["body"]["content"][0]["attrs"]["userIds"] == [987654]


class TestGetPostRedaction:
    async def test_another_user_gets_a_stub(self, auth_as, noted_post, other):
        client = auth_as(other)

        response = await client.get(f"/posts/{noted_post.id}")

        assert SECRET not in response.text
        assert "private words" not in response.text

    @pytest.mark.parametrize("viewer", ["author", "gm", "moderator"])
    async def test_those_who_may_read_notes_get_the_full_body(
        self, auth_as, noted_post, world, author, moderator, viewer
    ):
        client = auth_as({"author": author, "gm": world.gm}.get(viewer, moderator))

        response = await client.get(f"/posts/{noted_post.id}")

        # The author and moderator are who the edit form loads for.
        assert response.json()["body"] == noted_post.body


class TestThreadResponses:
    @pytest.mark.parametrize(
        "viewer, expected",
        [("gm", True), ("moderator", True), ("player", False)],
    )
    async def test_the_thread_says_whether_the_viewer_reads_every_note(
        self, auth_as, thread, noted_post, world, moderator, other, viewer, expected
    ):
        # noted_post gives the thread the first post the route needs.
        thread.first_post_id = noted_post.id
        thread.last_post_id = noted_post.id
        user = {"gm": world.gm, "moderator": moderator, "player": other}[viewer]
        client = auth_as(user)

        response = await client.get(f"/threads/{thread.id}")

        assert response.json()["sees_all_notes"] is expected

    async def test_thread_listings_carry_no_post_bodies(
        self, auth_as, create, db_session, other
    ):
        # A thread in the open site-root forum, which every listing shows.
        listed = await create(ThreadFactory)
        post = await create(
            PostFactory,
            thread=listed,
            body=doc(note(other.id + 1)),
            published_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await ThreadRepository(db_session, principal=None).attach_new_post(listed, post)
        client = auth_as(other)

        in_forum = await client.get("/threads", params={"forum_id": listed.forum_id})
        recent = await client.get("/threads/search", params={"scope": "latest"})

        for response in (in_forum, recent):
            assert response.status_code == 200
            assert response.json()["threads"]
            assert SECRET not in response.text
            assert "body" not in response.json()["threads"][0]["first_post"]

    async def test_the_announcement_is_redacted(self, auth_as, create, db_session):
        forum = await create(
            ForumFactory, id=ANNOUNCEMENTS_FORUM_ID, heritage=[SITE_ROOT_FORUM_ID]
        )
        await db_session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
                "(SELECT MAX(id) FROM forums))"
            )
        )
        thread = await create(ThreadFactory, forum=forum)
        reader = await create(UserFactory)
        post = await create(PostFactory, thread=thread, body=doc(note(), para("news")))
        thread.first_post_id = post.id
        thread.last_post_id = post.id
        await db_session.flush()
        client = auth_as(reader)

        response = await client.get("/threads/announcement")

        assert response.status_code == 200
        assert SECRET not in response.text


def new_post(thread, body):
    return {"thread_id": thread.id, "title": "Hello", "body": body}


class TestNoteWriteValidation:
    async def test_a_note_for_an_existing_user_is_saved_as_sent(
        self, auth_as, db_session, thread, author, recipient
    ):
        client = auth_as(author)
        body = doc(note(recipient.id, mode="private"))

        response = await client.post("/posts", json=new_post(thread, body))

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.body == body

    async def test_an_unknown_recipient_is_rejected(self, auth_as, thread, author):
        client = auth_as(author)

        response = await client.post("/posts", json=new_post(thread, doc(note(987654))))

        assert response.status_code == 400

    @pytest.mark.parametrize("user_id", [True, 0, 1.5])
    async def test_a_malformed_recipient_id_is_rejected(
        self, auth_as, thread, author, user_id
    ):
        client = auth_as(author)

        response = await client.post(
            "/posts", json=new_post(thread, doc(note(user_id)))
        )

        assert response.status_code == 400

    async def test_user_ids_that_isnt_a_list_is_rejected(self, auth_as, thread, author):
        client = auth_as(author)
        bad = {"type": "note", "attrs": {"userIds": "7"}, "content": [para("x")]}

        response = await client.post("/posts", json=new_post(thread, doc(bad)))

        assert response.status_code == 400

    async def test_twenty_recipients_are_fine_but_twenty_one_are_not(
        self, auth_as, create, thread, author
    ):
        users = [await create(UserFactory) for _ in range(21)]
        ids = [user.id for user in users]
        client = auth_as(author)

        twenty = await client.post(
            "/posts", json=new_post(thread, doc(note(*ids[:20])))
        )
        twenty_one = await client.post("/posts", json=new_post(thread, doc(note(*ids))))

        assert twenty.status_code == 200
        assert twenty_one.status_code == 400

    async def test_an_unknown_mode_is_rejected(self, auth_as, thread, author):
        client = auth_as(author)

        response = await client.post(
            "/posts", json=new_post(thread, doc(note(mode="secret")))
        )

        assert response.status_code == 400

    async def test_a_hidden_stub_nested_in_a_quote_is_rejected(
        self, auth_as, thread, author
    ):
        client = auth_as(author)
        quote = {"type": "quote", "content": [note(hidden=True)]}

        response = await client.post("/posts", json=new_post(thread, doc(quote)))

        assert response.status_code == 400

    async def test_an_edit_checks_the_notes(
        self, auth_as, create, thread, author, recipient
    ):
        post = await create(PostFactory, thread=thread, author=author)
        client = auth_as(author)
        edit = {"title": "Edited"}

        rejected = await client.patch(
            f"/posts/{post.id}", json={**edit, "body": doc(note(987654))}
        )
        stub = await client.patch(
            f"/posts/{post.id}", json={**edit, "body": doc(note(hidden=True))}
        )
        accepted = await client.patch(
            f"/posts/{post.id}", json={**edit, "body": doc(note(recipient.id))}
        )

        assert rejected.status_code == 400
        assert stub.status_code == 400
        assert accepted.status_code == 200

    async def test_a_new_thread_checks_its_notes(self, auth_as, thread, author):
        client = auth_as(author)
        base = {"forum_id": thread.forum_id, "title": "Hello"}

        rejected = await client.post(
            "/threads", json={**base, "body": doc(note(987654))}
        )
        accepted = await client.post("/threads", json={**base, "body": prose_doc("Hi")})

        assert rejected.status_code == 400
        assert accepted.status_code == 200
