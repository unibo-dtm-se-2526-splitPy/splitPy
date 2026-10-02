# splitPy

A Splitwise-like system for managing and splitting shared expenses within a group.
Software Engineering project work, Digital Transformation Management, University of Bologna.

The system is an **accounting ledger, not a payment system**: it records facts declared
by users, it does not move money.

## Components

| Component | Description |
|---|---|
| `splitpy-core` | Domain library: money arithmetic in cents, split strategies, balances, settlement, reporting. No framework dependencies. Published on PyPI |
| `splitpy-app` | Application layer and adapters: use cases, REST API (FastAPI), persistence (SQLAlchemy/PostgreSQL) |
| `splitpy-web` | Single-page application (React + TypeScript). Planned, milestone M9 |

## Architecture

Hexagonal (ports and adapters). Dependencies always point inwards: `splitpy-core`
imports nothing from `splitpy-app`. The repository port has two interchangeable
implementations, in-memory and SQLAlchemy, validated by the same contract test suite.

## Development

Requires Python 3.12+ and Poetry 2.x.

    cd splitpy-core && poetry install
    cd ../splitpy-app && poetry install

Run the test suite of either package with `poetry run pytest`.

Ruff lint fixes run automatically on commit via [pre-commit](https://pre-commit.com/).
Install it once per clone:

    pipx install pre-commit  # or: pip install pre-commit
    pre-commit install

## Authors

- Lorenzo Fattori - lorenzo.fattori2@studio.unibo.it
- Alessandro Grotti - alessandro.grotti@studio.unibo.it

## License

Apache-2.0 for code and artifacts, CC-BY-4.0 for the report.
