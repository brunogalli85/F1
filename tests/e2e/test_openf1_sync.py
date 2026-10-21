"""Testes contra a OpenF1 real. Rodam só com `pytest -m e2e` (precisam de rede)."""

from datetime import UTC, datetime

import pytest

from f1.config import Settings
from f1.domain.analysis import classification
from f1.infrastructure.openf1_client import OpenF1Client
from f1.pipelines.sync import sync_session

pytestmark = pytest.mark.e2e

QATAR_2024_RACE = 9655


@pytest.fixture
def client():
    settings = Settings.from_env()
    with OpenF1Client(
        settings.openf1_base_url,
        timeout_s=settings.http_timeout_s,
        min_interval_s=max(settings.min_request_interval_s, 1.0),
    ) as api:
        yield api


def test_operator_filters_work_against_the_real_api(client):
    podium = client.get("session_result", {"session_key": QATAR_2024_RACE, "position<=": 3})

    assert sorted(r["position"] for r in podium) == [1, 2, 3]


def test_empty_result_is_an_empty_list(client):
    assert client.get("session_result", {"session_key": QATAR_2024_RACE, "position>": 99}) == []


def test_sync_known_race_end_to_end(client, store):
    stats = sync_session(client, store, QATAR_2024_RACE, datetime.now(UTC))

    assert stats.sessions_synced == 1
    assert stats.rows_rejected == 0
    winner = classification(store.session_results(QATAR_2024_RACE))[0]
    assert winner.driver_number == 1
    assert len(store.laps(QATAR_2024_RACE)) == 944

    counts = store.table_counts()
    sync_session(client, store, QATAR_2024_RACE, datetime.now(UTC))
    assert {k: v for k, v in store.table_counts().items() if k != "sync_runs"} == {
        k: v for k, v in counts.items() if k != "sync_runs"
    }
