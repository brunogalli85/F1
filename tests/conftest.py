import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from f1.infrastructure.duckdb_store import DuckDbStore

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Callable[[str], list[dict[str, Any]]]:
    """Carrega uma resposta da OpenF1 salva em tests/fixtures/<nome>.json."""

    def _load(name: str) -> list[dict[str, Any]]:
        with (FIXTURES_DIR / f"{name}.json").open(encoding="utf-8") as fh:
            return json.load(fh)

    return _load


@pytest.fixture
def store() -> Iterator[DuckDbStore]:
    with DuckDbStore(":memory:") as db:
        yield db
