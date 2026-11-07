"""Id port: new ids come from here, so tests can make them predictable (RNF-02)."""

from typing import Protocol
from uuid import UUID


class IdGenerator(Protocol):
    def new_id(self) -> UUID: ...
