"""Errors as RFC 9457 problem details. Pure: the FastAPI exception handlers only wrap it."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from splitpy_core.domain.errors import (
    AlreadyAMember,
    DomainError,
    EntityNotFound,
    GroupArchived,
    NotAnAdministrator,
)
from splitpy_core.ports.group_repository import ConcurrencyConflict

PROBLEM_CONTENT_TYPE = "application/problem+json"
TYPE_BASE = "https://splitpy.example/errors/"

# A caller outside the group gets 403 from the membership guard before reaching the domain, so
# NotAMember here means a non-member payer or participant (I-03) and falls back to 422.
STATUS_BY_ERROR: Mapping[type[DomainError], int] = {
    NotAnAdministrator: 403,
    EntityNotFound: 404,
    GroupArchived: 409,
    AlreadyAMember: 409,
}
INVARIANT_VIOLATION = 422


class Unauthenticated(Exception):
    code: ClassVar[str] = "UNAUTHENTICATED"


# Not domain errors, but the client caused them and can act on them.
STATUS_BY_CLIENT_ERROR: Mapping[type[Exception], int] = {
    Unauthenticated: 401,
    ConcurrencyConflict: 409,
}


@dataclass(frozen=True, slots=True)
class Problem:
    type: str
    title: str
    status: int
    code: str
    detail: str
    instance: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def problem_for(error: Exception, instance: str) -> Problem:
    for cls, status in STATUS_BY_CLIENT_ERROR.items():
        if isinstance(error, cls):
            return _problem(cls.code, status, str(error), instance)
    if not isinstance(error, DomainError):
        # Never echo an unexpected error: its message may expose internal state.
        return _problem("INTERNAL_ERROR", 500, "An unexpected error occurred.", instance)
    return _problem(error.code, _status_for(error), str(error), instance)


def validation_problem(errors: Iterable[Mapping[str, Any]], instance: str) -> Problem:
    """Names each field without its location prefix (body, query), never echoing the input."""
    detail = "; ".join(f"{_field(error['loc'])}: {error['msg']}" for error in errors)
    return _problem("VALIDATION_ERROR", INVARIANT_VIOLATION, detail, instance)


def _field(loc: Sequence[object]) -> str:
    return ".".join(str(part) for part in loc[1:])


def _status_for(error: DomainError) -> int:
    """The most specific class in the hierarchy decides, so a subclass inherits its family."""
    for cls in type(error).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return INVARIANT_VIOLATION


def _problem(code: str, status: int, detail: str, instance: str) -> Problem:
    words = code.lower().split("_")
    return Problem(
        type=TYPE_BASE + "-".join(words),
        title=" ".join(words).capitalize(),
        status=status,
        code=code,
        detail=detail,
        instance=instance,
    )
