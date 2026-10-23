"""Domain errors as RFC 9457 problem details. Pure: the FastAPI exception handler only wraps it."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from splitpy_core.domain.errors import (
    AlreadyAMember,
    DomainError,
    EntityNotFound,
    GroupArchived,
    NotAnAdministrator,
)

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
    if not isinstance(error, DomainError):
        # Never echo an unexpected error: its message may expose internal state.
        return _problem("INTERNAL_ERROR", 500, "An unexpected error occurred.", instance)
    return _problem(error.code, _status_for(error), str(error), instance)


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
