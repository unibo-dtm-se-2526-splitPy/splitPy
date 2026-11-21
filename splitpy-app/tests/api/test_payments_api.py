"""Payment endpoints: record a reimbursement and list the recorded ones (RF-12)."""

from api_support import API, api_client, as_user
from support import ALICE, BOB, FIRST_ID, GROUP_ID, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork

PAYMENTS = f"{API}/groups/{GROUP_ID}/payments"
A, B = str(ALICE), str(BOB)


def bob_pays_alice(cents: int = 1500) -> dict[str, object]:
    return {
        "debtor": B,
        "creditor": A,
        "amount": {"cents": cents, "currency": "EUR"},
        "occurred_on": "2026-01-15",
    }


class TestRecordPayment:
    def test_rf12_recorded_payment_is_created(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)

        response = api_client(uow).post(PAYMENTS, json=bob_pays_alice(), headers=as_user(BOB))

        assert response.status_code == 201
        assert response.json() == {
            "id": str(FIRST_ID),
            "debtor": B,
            "creditor": A,
            "amount": {"cents": 1500, "currency": "EUR"},
            "occurred_on": "2026-01-15",
            "note": "",
        }

    def test_rf12_recorded_payments_are_listed(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        client = api_client(uow)
        client.post(PAYMENTS, json=bob_pays_alice(1500), headers=as_user(BOB))
        client.post(PAYMENTS, json=bob_pays_alice(500), headers=as_user(BOB))

        response = client.get(PAYMENTS, headers=as_user(ALICE))

        assert response.status_code == 200
        assert [payment["amount"]["cents"] for payment in response.json()] == [1500, 500]

    def test_rf12_payment_moves_the_balances(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        client = api_client(uow)

        client.post(PAYMENTS, json=bob_pays_alice(), headers=as_user(BOB))

        balances = client.get(f"{API}/groups/{GROUP_ID}/balances", headers=as_user(ALICE))
        assert balances.json() == {
            "by_member": {
                A: {"cents": -1500, "currency": "EUR"},
                B: {"cents": 1500, "currency": "EUR"},
            }
        }
