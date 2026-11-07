"""Time port: the domain never reads the system clock, use cases ask this one (RNF-02)."""

from datetime import date, datetime
from typing import Protocol


class Clock(Protocol):
    def today(self) -> date: ...

    def now(self) -> datetime: ...
