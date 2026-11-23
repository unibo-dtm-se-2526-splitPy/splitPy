"""Expense endpoints: register, list, read, change and remove (RF-06, RF-08, RF-09, RF-14)."""

from api_support import API, api_client, as_user
from fastapi.testclient import TestClient
from support import ALICE, BOB, CAROL, FIRST_ID, GROUP_ID, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork

EXPENSES = f"{API}/groups/{GROUP_ID}/expenses"
EXPENSE = f"{EXPENSES}/{FIRST_ID}"
A, B, C = str(ALICE), str(BOB), str(CAROL)


def dinner(
    cents: int = 3000, occurred_on: str = "2026-01-15", category: str = "FOOD", paid_by: str = A
) -> dict[str, object]:
    return {
        "description": "Dinner",
        "amount": {"cents": cents, "currency": "EUR"},
        "paid_by": paid_by,
        "category": category,
        "occurred_on": occurred_on,
        "split": {"type": "EQUAL", "participants": [A, B, C]},
    }


def client_of_the_flat() -> TestClient:
    uow = InMemoryUnitOfWork()
    stored_group(uow, BOB, CAROL)
    return api_client(uow)


def cents_listed(client: TestClient, query: str = "") -> list[int]:
    response = client.get(f"{EXPENSES}{query}", headers=as_user(BOB))
    return [expense["amount"]["cents"] for expense in response.json()["items"]]


class TestRegisterExpense:
    def test_rf06_expense_is_created_with_its_shares(self):
        response = client_of_the_flat().post(EXPENSES, json=dinner(), headers=as_user(ALICE))

        assert response.status_code == 201
        assert response.json() == {
            "id": str(FIRST_ID),
            **dinner(),
            "shares": {A: 1000, B: 1000, C: 1000},
        }

    def test_rf06_split_that_does_not_match_the_amount_is_rejected(self):
        expense = dinner() | {"split": {"type": "EXACT", "amounts": {A: 1000, B: 1000}}}

        response = client_of_the_flat().post(EXPENSES, json=expense, headers=as_user(ALICE))

        assert response.status_code == 422
        assert response.json()["code"] == "SPLIT_DOES_NOT_MATCH_AMOUNT"


class TestListExpenses:
    def test_rf14_expenses_are_listed_newest_first(self):
        client = client_of_the_flat()
        client.post(EXPENSES, json=dinner(3000, "2026-01-10"), headers=as_user(ALICE))
        client.post(EXPENSES, json=dinner(4500, "2026-01-20"), headers=as_user(ALICE))

        response = client.get(EXPENSES, headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json()["page"] == 1
        assert response.json()["size"] == 50
        assert cents_listed(client) == [4500, 3000]

    def test_rf14_expenses_are_filtered(self):
        client = client_of_the_flat()
        client.post(EXPENSES, json=dinner(1000, "2026-01-10"), headers=as_user(ALICE))
        client.post(EXPENSES, json=dinner(2000, "2026-01-20"), headers=as_user(ALICE))
        client.post(EXPENSES, json=dinner(3000, paid_by=B), headers=as_user(ALICE))
        client.post(EXPENSES, json=dinner(4000, category="TRANSPORT"), headers=as_user(ALICE))

        assert cents_listed(client, "?from=2026-01-11&to=2026-01-20") == [2000, 4000, 3000]
        assert cents_listed(client, f"?paid_by={B}") == [3000]
        assert cents_listed(client, "?category=TRANSPORT") == [4000]

    def test_rf14_expenses_are_paginated(self):
        client = client_of_the_flat()
        for day in ("10", "11", "12"):
            client.post(EXPENSES, json=dinner(int(day), f"2026-01-{day}"), headers=as_user(ALICE))

        assert cents_listed(client, "?page=2&size=2") == [10]

    def test_rf14_page_size_is_at_most_200(self):
        response = client_of_the_flat().get(f"{EXPENSES}?size=201", headers=as_user(BOB))

        assert response.status_code == 422


class TestOneExpense:
    def test_rf14_expense_detail(self):
        client = client_of_the_flat()
        client.post(EXPENSES, json=dinner(), headers=as_user(ALICE))

        response = client.get(EXPENSE, headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json()["id"] == str(FIRST_ID)

    def test_rf08_only_the_fields_sent_change(self):
        client = client_of_the_flat()
        client.post(EXPENSES, json=dinner(), headers=as_user(ALICE))
        exact = {"type": "EXACT", "amounts": {A: 2000, B: 1000}}

        response = client.patch(EXPENSE, json={"split": exact}, headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json()["description"] == "Dinner"
        assert response.json()["shares"] == {A: 2000, B: 1000}

    def test_rf09_removed_expense_is_gone(self):
        client = client_of_the_flat()
        client.post(EXPENSES, json=dinner(), headers=as_user(ALICE))

        removed = client.delete(EXPENSE, headers=as_user(BOB))

        assert removed.status_code == 204
        assert client.get(EXPENSE, headers=as_user(BOB)).json()["code"] == "EXPENSE_NOT_FOUND"
        assert cents_listed(client) == []

    def test_unknown_expense_is_not_found(self):
        response = client_of_the_flat().get(EXPENSE, headers=as_user(BOB))

        assert response.status_code == 404
        assert response.json()["code"] == "EXPENSE_NOT_FOUND"
