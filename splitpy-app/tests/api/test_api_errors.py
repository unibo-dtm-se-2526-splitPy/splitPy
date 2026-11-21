"""Every error leaves the API as an RFC 9457 problem, with its HTTP status and stable code."""

from uuid import UUID

from api_support import API, api_client, as_user
from fastapi.testclient import TestClient
from support import ALICE, BOB, GROUP_ID, FixedClock, SequentialIds, load, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.adapters.rest.app import create_app
from splitpy_app.adapters.rest.dependencies import Services
from splitpy_app.adapters.rest.problems import PROBLEM_CONTENT_TYPE

PAYMENTS = f"{API}/groups/{GROUP_ID}/payments"
PAYMENT = {
    "debtor": str(BOB),
    "creditor": str(ALICE),
    "amount": {"cents": 1500, "currency": "EUR"},
    "occurred_on": "2026-01-15",
}


def group_of_alice_and_bob() -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    stored_group(uow, BOB)
    return uow


def test_a_request_without_user_is_unauthenticated():
    response = api_client(group_of_alice_and_bob()).get(PAYMENTS)

    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_a_user_id_that_is_not_a_uuid_is_unauthenticated():
    response = api_client(group_of_alice_and_bob()).get(PAYMENTS, headers={"X-User-Id": "alice"})

    assert response.status_code == 401


def test_rf12_unknown_group_is_not_found():
    unknown = UUID(int=99)

    response = api_client(group_of_alice_and_bob()).get(
        f"{API}/groups/{unknown}/payments", headers=as_user(ALICE)
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json() == {
        "type": "https://splitpy.example/errors/group-not-found",
        "title": "Group not found",
        "status": 404,
        "code": "GROUP_NOT_FOUND",
        "detail": response.json()["detail"],
        "instance": f"{API}/groups/{unknown}/payments",
    }


def test_rnf01_amount_with_decimals_is_a_validation_error():
    payment = PAYMENT | {"amount": {"cents": 15.5, "currency": "EUR"}}

    response = api_client(group_of_alice_and_bob()).post(
        PAYMENTS, json=payment, headers=as_user(BOB)
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "amount.cents" in response.json()["detail"]


def test_rf12_domain_rule_broken_by_the_request_is_unprocessable():
    payment = PAYMENT | {"creditor": str(BOB)}

    response = api_client(group_of_alice_and_bob()).post(
        PAYMENTS, json=payment, headers=as_user(BOB)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PAYMENT"


def test_rf16_writing_to_an_archived_group_is_a_conflict():
    uow = group_of_alice_and_bob()
    group = load(uow)
    group.archive(by=ALICE)
    group.pull_events()
    with uow:
        uow.groups.save(group)
        uow.commit()

    response = api_client(uow).post(PAYMENTS, json=PAYMENT, headers=as_user(BOB))

    assert response.status_code == 409
    assert response.json()["code"] == "GROUP_ARCHIVED"


def test_unexpected_error_is_500_without_internal_details():
    def broken_units():
        raise RuntimeError("database password is hunter2")

    services = Services(units=broken_units, clock=FixedClock(), ids=SequentialIds())
    client = TestClient(create_app(services), raise_server_exceptions=False)

    response = client.get(PAYMENTS, headers=as_user(ALICE))

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text
