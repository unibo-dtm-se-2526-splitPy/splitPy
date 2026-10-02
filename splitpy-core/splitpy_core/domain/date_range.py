"""A period of days with both extremes included."""

from dataclasses import dataclass
from datetime import date

from splitpy_core.domain.errors import InvalidDateRange


@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise InvalidDateRange(f"start {self.start} is after end {self.end}")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end
