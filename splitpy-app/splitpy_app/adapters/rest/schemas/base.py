"""Base of every request and response schema."""

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """A field the client sends by mistake is an error, not something silently dropped."""

    model_config = ConfigDict(extra="forbid", frozen=True)
