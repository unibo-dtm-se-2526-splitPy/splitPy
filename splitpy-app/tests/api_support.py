"""The API on an in-memory unit of work, for the tests of the routers."""

from fastapi.testclient import TestClient
from support import FixedClock, SequentialIds

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.adapters.rest.app import Services, create_app
from splitpy_core.domain.ids import UserId

API = "/api/v1"


def api_client(uow: InMemoryUnitOfWork) -> TestClient:
    """Fixed clock and sequential ids, as in the tests of the use cases."""
    services = Services(units=lambda: uow, clock=FixedClock(), ids=SequentialIds())
    return TestClient(create_app(services))


def as_user(user: UserId) -> dict[str, str]:
    return {"X-User-Id": str(user)}
