"""Balances, settlement plan, report and activity feed, computed on every request."""

from datetime import date
from uuid import UUID

from api_support import API, api_client, as_user
from support import ALICE, BOB, CAROL, DAY, GROUP_ID, eur, load, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_core.domain.category import Category
from splitpy_core.domain.ids import ExpenseId
from splitpy_core.domain.split import EqualSplit

GROUP = f"{API}/groups/{GROUP_ID}"
A, B, C = str(ALICE), str(BOB), str(CAROL)


def euros(cents: int) -> dict[str, object]:
    return {"cents": cents, "currency": "EUR"}


def group_with_dinner(occurred_on: date = DAY) -> InMemoryUnitOfWork:
    """A dinner of 30.00 paid by Alice and split equally among Alice, Bob and Carol."""
    uow = InMemoryUnitOfWork()
    stored_group(uow, BOB, CAROL)
    group = load(uow)
    group.register_expense(
        ExpenseId(UUID(int=100)),
        "Dinner",
        eur("30.00"),
        ALICE,
        EqualSplit(frozenset({ALICE, BOB, CAROL})),
        Category.FOOD,
        occurred_on,
        by=ALICE,
    )
    group.pull_events()
    with uow:
        uow.groups.save(group)
        uow.commit()
    return uow


class TestBalances:
    def test_rf10_every_active_member_has_a_balance(self):
        response = api_client(group_with_dinner()).get(f"{GROUP}/balances", headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json() == {"by_member": {A: euros(2000), B: euros(-1000), C: euros(-1000)}}


class TestSettlement:
    def test_rf11_plan_brings_every_balance_to_zero(self):
        response = api_client(group_with_dinner()).get(f"{GROUP}/settlement", headers=as_user(BOB))

        assert response.status_code == 200
        assert response.json() == {
            "transfers": [
                {"debtor": B, "creditor": A, "amount": euros(1000)},
                {"debtor": C, "creditor": A, "amount": euros(1000)},
            ]
        }


class TestReport:
    def test_rf13_report_covers_the_requested_period(self):
        client = api_client(group_with_dinner())

        response = client.get(
            f"{GROUP}/report",
            params={"from": "2026-01-01", "to": "2026-01-31"},
            headers=as_user(BOB),
        )

        assert response.status_code == 200
        assert response.json() == {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "total": euros(3000),
            "by_category": {"FOOD": euros(3000)},
            "by_member": {A: euros(1000), B: euros(1000), C: euros(1000)},
        }

    def test_rf13_period_ending_before_it_starts_is_unprocessable(self):
        client = api_client(group_with_dinner())

        response = client.get(
            f"{GROUP}/report",
            params={"from": "2026-02-01", "to": "2026-01-01"},
            headers=as_user(BOB),
        )

        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_DATE_RANGE"

    def test_rf13_both_extremes_are_required(self):
        client = api_client(group_with_dinner())

        response = client.get(
            f"{GROUP}/report", params={"from": "2026-01-01"}, headers=as_user(BOB)
        )

        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


class TestActivity:
    def record_payments(self, client, *amounts: int) -> None:
        for cents in amounts:
            client.post(
                f"{GROUP}/payments",
                json={
                    "debtor": B,
                    "creditor": A,
                    "amount": euros(cents),
                    "occurred_on": "2026-01-15",
                },
                headers=as_user(BOB),
            )

    def test_rf15_feed_shows_the_recorded_events_with_their_instant(self):
        client = api_client(group_with_dinner())
        self.record_payments(client, 1000)

        response = client.get(f"{GROUP}/activity", headers=as_user(ALICE))

        assert response.status_code == 200
        [entry] = response.json()["items"]
        assert entry["type"] == "PaymentRecorded"
        assert entry["at"] == "2026-02-01T12:00:00Z"
        assert entry["data"] == {
            "payment_id": entry["data"]["payment_id"],
            "debtor": B,
            "creditor": A,
            "amount": euros(1000),
            "by": B,
        }

    def test_rf15_feed_is_paginated_newest_first(self):
        client = api_client(group_with_dinner())
        self.record_payments(client, 100, 200, 300)

        pages = [
            client.get(
                f"{GROUP}/activity", params={"page": page, "size": 2}, headers=as_user(ALICE)
            ).json()
            for page in (1, 2)
        ]

        assert [[e["data"]["amount"]["cents"] for e in p["items"]] for p in pages] == [
            [300, 200],
            [100],
        ]
        assert [(p["page"], p["size"]) for p in pages] == [(1, 2), (2, 2)]

    def test_rf15_page_size_is_at_most_200(self):
        client = api_client(group_with_dinner())

        response = client.get(f"{GROUP}/activity", params={"size": 201}, headers=as_user(ALICE))

        assert response.status_code == 422
