import pytest

from app.models import FAQ, RolePermission
from tests.factories import FAQFactory, RoleFactory, prose_doc

Verbs = RolePermission.ValidPermissions
Categories = FAQ.Categories


@pytest.fixture
async def faq_admin_client(authed_client, db_session):
    client, user = authed_client
    role = RoleFactory.build(owner=user)
    db_session.add(role)
    role.grant(Verbs.MANAGE_FAQS)
    user.roles.append(role)
    await db_session.flush()
    return client


def faq_body(**overrides):
    return {
        "category": "games",
        "question": "How do I join a game?",
        "answer": prose_doc("Click join."),
        **overrides,
    }


class TestGetFAQs:
    async def test_groups_by_category_in_order(self, client, create):
        await create(FAQFactory, category=Categories.TOOLS, question="T1", order=1)
        await create(FAQFactory, category=Categories.GAMES, question="G2", order=2)
        await create(FAQFactory, category=Categories.GAMES, question="G1", order=1)

        response = await client.get("/faqs")

        assert response.status_code == 200
        categories = response.json()["categories"]
        assert [(c["category"], c["label"]) for c in categories] == [
            ("getting-started", "Getting Started"),
            ("characters", "Characters"),
            ("games", "Games"),
            ("tools", "Tools"),
        ]
        by_slug = {c["category"]: c["faqs"] for c in categories}
        assert by_slug["getting-started"] == []
        assert by_slug["characters"] == []
        assert [f["question"] for f in by_slug["games"]] == ["G1", "G2"]
        assert [f["question"] for f in by_slug["tools"]] == ["T1"]
        assert set(by_slug["tools"][0]) == {
            "id",
            "category",
            "question",
            "answer",
            "order",
        }


class TestRequiresManageFAQs:
    # The permission check itself is covered in test_middleware.py; this guards
    # that every write route actually carries @requires("manage_faqs").
    @pytest.mark.parametrize(
        "method, path, body",
        [
            ("POST", "/faqs", faq_body()),
            ("PUT", "/faqs/1", faq_body()),
            ("DELETE", "/faqs/1", None),
            ("POST", "/faqs/1/move", {"direction": "up"}),
        ],
    )
    async def test_forbidden_without_permission(
        self, authed_client, method, path, body
    ):
        client, _user = authed_client

        response = await client.request(method, path, json=body)

        assert response.status_code == 403


class TestCreateFAQ:
    async def test_creates_with_trimmed_question(self, faq_admin_client):
        response = await faq_admin_client.post(
            "/faqs", json=faq_body(question="  Padded?  ")
        )

        assert response.status_code == 201
        body = response.json()
        assert body["question"] == "Padded?"
        assert body["category"] == "games"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"question": "   "},
            {"answer": {"type": "doc", "content": []}},
            {"answer": prose_doc("   ")},
            {"answer": {"type": "paragraph", "content": prose_doc("x")["content"]}},
        ],
    )
    async def test_rejects_invalid_input(self, faq_admin_client, overrides):
        response = await faq_admin_client.post("/faqs", json=faq_body(**overrides))

        assert response.status_code == 422

    async def test_accepts_non_text_answer_content(self, faq_admin_client):
        answer = {"type": "doc", "content": [{"type": "horizontalRule"}]}

        response = await faq_admin_client.post("/faqs", json=faq_body(answer=answer))

        assert response.status_code == 201


class TestUpdateFAQ:
    async def test_updates_fields_in_place(self, faq_admin_client, create):
        faq = await create(FAQFactory, category=Categories.GAMES, order=1)

        response = await faq_admin_client.put(
            f"/faqs/{faq.id}",
            json=faq_body(question="New?", answer=prose_doc("New answer")),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["question"] == "New?"
        assert body["answer"] == prose_doc("New answer")
        assert body["order"] == 1

    async def test_unknown_faq_is_404(self, faq_admin_client):
        response = await faq_admin_client.put("/faqs/999999", json=faq_body())

        assert response.status_code == 404


class TestDeleteFAQ:
    async def test_deletes(self, faq_admin_client, create, client):
        faq = await create(FAQFactory, category=Categories.GAMES, order=1)

        response = await faq_admin_client.delete(f"/faqs/{faq.id}")

        assert response.status_code == 204
        listing = (await client.get("/faqs")).json()["categories"]
        assert all(c["faqs"] == [] for c in listing)


class TestMoveFAQ:
    async def test_move_down_swaps_with_next(self, faq_admin_client, create, client):
        first = await create(FAQFactory, category=Categories.GAMES, order=1)
        await create(FAQFactory, category=Categories.GAMES, order=2)

        response = await faq_admin_client.post(
            f"/faqs/{first.id}/move", json={"direction": "down"}
        )

        assert response.status_code == 204
        games = (await client.get("/faqs")).json()["categories"][2]["faqs"]
        assert games[-1]["id"] == first.id
