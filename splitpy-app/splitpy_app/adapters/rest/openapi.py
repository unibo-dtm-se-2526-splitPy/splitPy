"""Writes the OpenAPI spec of the API, committed in docs/openapi.json (the design, §08)."""

import json
import sys
from pathlib import Path

from splitpy_app.adapters.rest.app import api


def spec_text() -> str:
    return json.dumps(api().openapi(), indent=2) + "\n"


def main(argv: list[str]) -> None:
    Path(argv[0]).write_text(spec_text())


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
