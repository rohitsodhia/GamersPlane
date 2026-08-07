from tests.factories import PMFactory, UserFactory, prose_doc


class TestGetPMs:
    async def test_get_pms_requires_auth(self, client):
        response = await client.get("/pms")

        assert response.status_code == 403

    async def test_get_pms_returns_inbox_by_default(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        await create(PMFactory, recipient=user, sender=other, title="Hello")

        response = await client.get("/pms")

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["page"] == 1
        assert len(body["pms"]) == 1
        pm = body["pms"][0]
        assert pm["title"] == "Hello"
        assert pm["sender"]["username"] == "other"
        assert pm["recipient"]["username"] == user.username

    async def test_get_pms_outbox(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        await create(PMFactory, recipient=other, sender=user, title="Sent")
        await create(PMFactory, recipient=user, sender=other, title="Received")

        response = await client.get("/pms", params={"box": "outbox"})

        body = response.json()
        assert [pm["title"] for pm in body["pms"]] == ["Sent"]

    async def test_get_pms_empty(self, authed_client):
        client, _user = authed_client

        response = await client.get("/pms")

        body = response.json()
        assert body["pms"] == []
        assert body["count"] == 0

    async def test_get_pms_page_below_one_is_clamped(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        await create(PMFactory, recipient=user, sender=other)

        response = await client.get("/pms", params={"page": 0})

        assert response.status_code == 200
        assert response.json()["page"] == 1

    async def test_get_pms_respects_limit(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        for i in range(3):
            await create(PMFactory, recipient=user, sender=other, title=f"PM {i}")

        response = await client.get("/pms", params={"limit": 2})

        body = response.json()
        assert len(body["pms"]) == 2
        assert body["count"] == 3
        assert body["limit"] == 2

    async def test_get_pms_second_page(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        for i in range(3):
            await create(PMFactory, recipient=user, sender=other, title=f"PM {i}")

        response = await client.get("/pms", params={"limit": 2, "page": 2})

        body = response.json()
        assert body["page"] == 2
        assert len(body["pms"]) == 1
        assert body["count"] == 3


class TestGetPM:
    async def test_get_pm_requires_auth(self, client, create):
        alice = await create(UserFactory, username="alice")
        bob = await create(UserFactory, username="bob")
        pm = await create(PMFactory, recipient=alice, sender=bob)

        response = await client.get(f"/pms/{pm.id}")

        assert response.status_code == 403

    async def test_get_pm_as_recipient_marks_recipient_read(
        self, authed_client, create
    ):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        pm = await create(
            PMFactory,
            recipient=user,
            sender=other,
            title="Hello",
            message=prose_doc("Hi there"),
        )

        response = await client.get(f"/pms/{pm.id}")

        assert response.status_code == 200
        body = response.json()["pm"]
        assert body["title"] == "Hello"
        assert body["message"] == prose_doc("Hi there")
        assert body["recipient"]["read"] is True
        assert body["sender"]["read"] is False

    async def test_get_pm_as_sender_marks_sender_read(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        pm = await create(PMFactory, recipient=other, sender=user)

        response = await client.get(f"/pms/{pm.id}")

        body = response.json()["pm"]
        assert body["sender"]["read"] is True
        assert body["recipient"]["read"] is False

    async def test_get_pm_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.get("/pms/999999")

        assert response.status_code == 404

    async def test_get_pm_forbidden_for_uninvolved_user(self, authed_client, create):
        client, _user = authed_client
        alice = await create(UserFactory, username="alice")
        bob = await create(UserFactory, username="bob")
        pm = await create(PMFactory, recipient=alice, sender=bob)

        response = await client.get(f"/pms/{pm.id}")

        assert response.status_code == 404

    async def test_get_pm_includes_history(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        original = await create(
            PMFactory, recipient=user, sender=other, title="Original"
        )
        reply = await create(
            PMFactory,
            recipient=other,
            sender=user,
            title="Reply",
            reply_to_id=original.id,
            history_ids=[original.id],
        )

        response = await client.get(f"/pms/{reply.id}")

        body = response.json()["pm"]
        assert [h["title"] for h in body["history"]] == ["Original"]

    async def test_get_pm_history_excludes_entries_principal_is_not_part_of(
        self, authed_client, create
    ):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        stranger = await create(UserFactory, username="stranger")
        unrelated = await create(
            PMFactory, recipient=other, sender=stranger, title="Unrelated"
        )
        reply = await create(
            PMFactory,
            recipient=other,
            sender=user,
            title="Reply",
            history_ids=[unrelated.id],
        )

        response = await client.get(f"/pms/{reply.id}")

        body = response.json()["pm"]
        assert body["history"] == []

    async def test_get_pm_include_self_history_prepends_current_pm(
        self, authed_client, create
    ):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        original = await create(
            PMFactory, recipient=user, sender=other, title="Original"
        )
        reply = await create(
            PMFactory,
            recipient=other,
            sender=user,
            title="Reply",
            reply_to_id=original.id,
            history_ids=[original.id],
        )

        response = await client.get(
            f"/pms/{reply.id}", params={"include_self_history": True}
        )

        body = response.json()["pm"]
        assert [h["title"] for h in body["history"]] == ["Reply", "Original"]


class TestSendPM:
    async def test_send_pm(self, authed_client, create):
        client, _user = authed_client
        recipient = await create(UserFactory, username="recipient")

        response = await client.post(
            "/pms",
            json={
                "username": recipient.username,
                "title": "Hello",
                "message": prose_doc("Hi there"),
            },
        )

        assert response.status_code == 200
        assert response.json()["sent"] is True

    async def test_send_pm_requires_auth(self, client, create):
        recipient = await create(UserFactory, username="recipient")

        response = await client.post(
            "/pms",
            json={
                "username": recipient.username,
                "title": "Hello",
                "message": prose_doc("Hi there"),
            },
        )

        assert response.status_code == 403

    async def test_send_pm_no_recipient(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/pms",
            json={
                "username": "nobody",
                "title": "Hello",
                "message": prose_doc("Hi there"),
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "no_recipient"

    async def test_send_pm_to_self(self, authed_client):
        client, user = authed_client

        response = await client.post(
            "/pms",
            json={
                "username": user.username,
                "title": "Hello",
                "message": prose_doc("Hi there"),
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "pm_self"

    async def test_send_pm_strips_whitespace_from_title_on_read(
        self, authed_client, create
    ):
        client, _user = authed_client
        recipient = await create(UserFactory, username="recipient")

        response = await client.post(
            "/pms",
            json={
                "username": recipient.username,
                "title": "  Hello\nthere  ",
                "message": prose_doc("Hi there"),
            },
        )

        assert response.status_code == 200

        list_response = await client.get("/pms", params={"box": "outbox"})
        title = list_response.json()["pms"][0]["title"]
        assert title == "Hello<br>there"

    async def test_send_pm_reply_links_history(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        original = await create(
            PMFactory, recipient=user, sender=other, title="Original"
        )

        response = await client.post(
            "/pms",
            json={
                "username": other.username,
                "title": "Reply",
                "message": prose_doc("Hi there"),
                "reply_to_id": original.id,
            },
        )

        assert response.status_code == 200

        list_response = await client.get("/pms", params={"box": "outbox"})
        pm = list_response.json()["pms"][0]
        reply_id = pm["id"]

        get_response = await client.get(f"/pms/{reply_id}")
        body = get_response.json()["pm"]
        assert body["reply_to_id"] == original.id
        assert [h["title"] for h in body["history"]] == ["Original"]

    async def test_send_pm_with_inaccessible_reply_to_id_creates_standalone_pm(
        self, authed_client, create
    ):
        client, _user = authed_client
        recipient = await create(UserFactory, username="recipient")
        alice = await create(UserFactory, username="alice")
        bob = await create(UserFactory, username="bob")
        unrelated = await create(PMFactory, recipient=alice, sender=bob)

        response = await client.post(
            "/pms",
            json={
                "username": recipient.username,
                "title": "Reply",
                "message": prose_doc("Hi there"),
                "reply_to_id": unrelated.id,
            },
        )

        assert response.status_code == 200

        list_response = await client.get("/pms", params={"box": "outbox"})
        pm = list_response.json()["pms"][0]

        get_response = await client.get(f"/pms/{pm['id']}")
        body = get_response.json()["pm"]
        assert body["reply_to_id"] is None
        assert body["history"] == []


class TestDeletePM:
    async def test_delete_pm_requires_auth(self, client, create):
        alice = await create(UserFactory, username="alice")
        bob = await create(UserFactory, username="bob")
        pm = await create(PMFactory, recipient=alice, sender=bob)

        response = await client.delete(f"/pms/{pm.id}")

        assert response.status_code == 403

    async def test_delete_pm_as_recipient(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        pm = await create(PMFactory, recipient=user, sender=other)

        response = await client.delete(f"/pms/{pm.id}")

        assert response.status_code == 204

    async def test_delete_pm_as_sender(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        pm = await create(PMFactory, recipient=other, sender=user)

        response = await client.delete(f"/pms/{pm.id}")

        assert response.status_code == 204

        list_response = await client.get("/pms", params={"box": "outbox"})
        assert list_response.json()["pms"] == []

    async def test_delete_pm_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/pms/999999")

        assert response.status_code == 404
