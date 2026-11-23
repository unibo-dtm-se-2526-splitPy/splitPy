"""The committed OpenAPI spec is the one the code generates (the design, §08)."""

import json
from pathlib import Path

from splitpy_app.adapters.rest.openapi import main, spec_text

COMMITTED = Path(__file__).parents[3] / "docs" / "openapi.json"


def test_rnf06_committed_spec_matches_the_code():
    # If this fails: poetry run python -m splitpy_app.adapters.rest.openapi ../docs/openapi.json
    assert COMMITTED.read_text() == spec_text()


def test_rnf06_export_writes_the_spec(tmp_path):
    target = tmp_path / "openapi.json"
    main([str(target)])
    assert target.read_text() == spec_text()


def test_rnf06_every_route_is_under_api_v1():
    paths = json.loads(spec_text())["paths"]
    assert len(paths) == 11
    assert all(path.startswith("/api/v1/groups") for path in paths)


def test_rnf06_spec_version_is_the_api_version_in_the_path():
    assert json.loads(spec_text())["info"]["version"] == "1"
