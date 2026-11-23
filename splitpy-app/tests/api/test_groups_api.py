"""Group endpoints: create, list, read, archive and manage the members (RF-04, RF-05, RF-16)."""

from api_support import API, api_client, as_user
from support import ALICE, BOB, CAROL, FIRST_ID, GROUP_ID, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork

GROUPS = f"{API}/groups"
GROUP = f"{GROUPS}/{GROUP_ID}"
A, B, C = str(ALICE), str(BOB), str(CAROL)


def member(user: str, role: str = "MEMBER", left_at: str | None = None) -> dict[str, object]:
    """Members of the stored group joined at T0."""
    return {"user_id": user, "role": role, "joined_at": "2026-01-01T00:00:00Z", "left_at": left_at}


def group_of_alice_and_bob() -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    stored_group(uow, BOB)
    return uow


class TestCreateGroup:
    def test_rf04_group_is_created_with_the_caller_as_admin(self):
        response = api_client(InMemoryUnitOfWork()).post(
            GROUPS, json={"name": "Trip", "currency": "EUR"}, headers=as_user(ALICE)
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": str(FIRST_ID),
            "name": "Trip",
            "currency": "EUR",
            "status": "ACTIVE",
            "members": [
                {
                    "user_id": A,
                    "role": "ADMIN",
                    "joined_at": "2026-02-01T12:00:00Z",
                    "left_at": None,
                }
            ],
        }

    def test_rf04_unsupported_currency_is_rejected(self):
        response = api_client(InMemoryUnitOfWork()).post(
            GROUPS, json={"name": "Trip", "currency": "XYZ"}, headers=as_user(ALICE)
        )

        assert response.status_code == 422
        assert response.json()["code"] == "UNSUPPORTED_CURRENCY"


class TestReadGroups:
    def test_rf04_caller_lists_the_groups_they_belong_to(self):
        response = api_client(group_of_alice_and_bob()).get(GROUPS, headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json() == [
            {"id": str(GROUP_ID), "name": "Flat", "currency": "EUR", "status": "ACTIVE"}
        ]

    def test_rf04_group_detail_lists_the_members(self):
        response = api_client(group_of_alice_and_bob()).get(GROUP, headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json()["members"] == [member(A, "ADMIN"), member(B)]

    def test_unknown_group_is_not_found(self):
        response = api_client(InMemoryUnitOfWork()).get(GROUP, headers=as_user(ALICE))

        assert response.status_code == 404
        assert response.json()["code"] == "GROUP_NOT_FOUND"


class TestArchiveGroup:
    def test_rf16_admin_archives_the_group(self):
        response = api_client(group_of_alice_and_bob()).patch(
            GROUP, json={"status": "ARCHIVED"}, headers=as_user(ALICE)
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ARCHIVED"

    def test_rf16_archived_group_cannot_be_archived_again(self):
        client = api_client(group_of_alice_and_bob())
        client.patch(GROUP, json={"status": "ARCHIVED"}, headers=as_user(ALICE))

        response = client.patch(GROUP, json={"status": "ARCHIVED"}, headers=as_user(ALICE))

        assert response.status_code == 409
        assert response.json()["code"] == "GROUP_ARCHIVED"

    def test_rf16_group_cannot_be_reactivated(self):
        response = api_client(group_of_alice_and_bob()).patch(
            GROUP, json={"status": "ACTIVE"}, headers=as_user(ALICE)
        )

        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


class TestMembers:
    def test_rf05_admin_adds_a_member(self):
        response = api_client(group_of_alice_and_bob()).post(
            f"{GROUP}/members", json={"user_id": C}, headers=as_user(ALICE)
        )

        assert response.status_code == 201
        assert [m["user_id"] for m in response.json()["members"]] == [A, B, C]

    def test_rf05_only_the_admin_adds_members(self):
        response = api_client(group_of_alice_and_bob()).post(
            f"{GROUP}/members", json={"user_id": C}, headers=as_user(BOB)
        )

        assert response.status_code == 403
        assert response.json()["code"] == "NOT_AN_ADMINISTRATOR"

    def test_rf05_admin_removes_a_member(self):
        client = api_client(group_of_alice_and_bob())

        response = client.delete(f"{GROUP}/members/{B}", headers=as_user(ALICE))

        assert response.status_code == 204
        members = client.get(GROUP, headers=as_user(ALICE)).json()["members"]
        assert members[1] == member(B, left_at="2026-02-01T12:00:00Z")

    def test_rf05_admin_leaving_names_a_successor(self):
        client = api_client(group_of_alice_and_bob())

        refused = client.delete(f"{GROUP}/members/{A}", headers=as_user(ALICE))
        removed = client.delete(f"{GROUP}/members/{A}?successor={B}", headers=as_user(ALICE))

        assert refused.json()["code"] == "ADMIN_SUCCESSOR_REQUIRED"
        assert removed.status_code == 204
