"""What the routers receive from FastAPI: the acting user and the services of the use cases."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from splitpy_app.adapters.rest.problems import Unauthenticated
from splitpy_app.application.ports import UnitOfWork
from splitpy_core.domain.ids import UserId
from splitpy_core.ports.clock import Clock
from splitpy_core.ports.id_generator import IdGenerator


@dataclass(frozen=True, slots=True)
class Services:
    """units builds the unit of work of one request: a database session cannot be shared."""

    units: Callable[[], UnitOfWork]
    clock: Clock
    ids: IdGenerator


def services(request: Request) -> Services:
    return request.app.state.services


def current_user(x_user_id: Annotated[str | None, Header()] = None) -> UserId:
    """Until the JWT arrives (M7) the caller names itself in X-User-Id; only this changes then."""
    if x_user_id is None:
        raise Unauthenticated("missing X-User-Id header")
    try:
        return UserId(UUID(x_user_id))
    except ValueError:
        raise Unauthenticated("X-User-Id is not a UUID") from None


CurrentUser = Annotated[UserId, Depends(current_user)]
AppServices = Annotated[Services, Depends(services)]
