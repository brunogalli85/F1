from datetime import UTC, datetime

import pytest

from f1.pipelines.sync import SyncError, sync_session, sync_year

AFTER_SEASON = datetime(2025, 1, 1, tzinfo=UTC)
# Entre o sprint (sábado) e a corrida (domingo) do GP do Catar 2024.
DURING_WEEKEND = datetime(2024, 12, 1, 12, 0, tzinfo=UTC)


class FakeOpenF1Client:
    """Cliente falso que responde com as fixtures, filtrando por igualdade."""

    def __init__(self, load_fixture, overrides=None):
        race = load_fixture("session_result_race")
        quali = load_fixture("session_result_qualifying")
        self.data = {
            "meetings": load_fixture("meetings"),
            "sessions": load_fixture("sessions"),
            "drivers": [
                {**d, "session_key": key} for key in (9646, 9655) for d in load_fixture("drivers")
            ],
            "session_result": race + quali,
            "laps": load_fixture("laps"),
            "stints": load_fixture("stints"),
            "pit": load_fixture("pit"),
            **(overrides or {}),
        }
        self.calls = []

    def get(self, endpoint, filters=None):
        filters = dict(filters or {})
        self.calls.append((endpoint, filters))
        return [
            record
            for record in self.data[endpoint]
            if all(record.get(field) == value for field, value in filters.items())
        ]


@pytest.fixture
def client(load_fixture):
    return FakeOpenF1Client(load_fixture)


def test_sync_year_loads_finished_sessions(client, store):
    stats = sync_year(client, store, 2024, AFTER_SEASON)

    counts = store.table_counts()
    assert stats.sessions_synced == 5
    assert stats.sessions_skipped == 0
    assert counts["meetings"] == 1
    assert counts["sessions"] == 5
    assert counts["session_results"] == 8
    assert counts["laps"] == 5
    assert counts["sync_runs"] == 1
    assert stats.rows_rejected == 0
    assert stats.rows_read == sum(len(v) for v in client.data.values())


def test_sync_year_rerun_does_not_duplicate_rows(client, store):
    sync_year(client, store, 2024, AFTER_SEASON)
    first = store.table_counts()

    sync_year(client, store, 2024, AFTER_SEASON)
    second = store.table_counts()

    assert {k: v for k, v in second.items() if k != "sync_runs"} == {
        k: v for k, v in first.items() if k != "sync_runs"
    }
    assert second["sync_runs"] == 2


def test_sync_year_filters_by_session_type(client, store):
    stats = sync_year(client, store, 2024, AFTER_SEASON, session_type="Race")

    assert ("sessions", {"year": 2024, "session_type": "Race"}) in client.calls
    assert stats.sessions_synced == 2


def test_sync_year_skips_unfinished_and_cancelled_sessions(load_fixture, store):
    sessions = load_fixture("sessions")
    sessions[0] = {**sessions[0], "is_cancelled": True}
    client = FakeOpenF1Client(load_fixture, {"sessions": sessions})

    stats = sync_year(client, store, 2024, DURING_WEEKEND)

    synced = {f["session_key"] for endpoint, f in client.calls if endpoint == "laps"}
    assert synced == {9650, 9646, 9654}
    assert stats.sessions_skipped == 2
    assert store.table_counts()["sessions"] == 5  # metadados de todas as sessões continuam no cache


def test_sync_year_accepts_sessions_without_results_yet(load_fixture, store):
    client = FakeOpenF1Client(load_fixture, {"session_result": []})

    stats = sync_year(client, store, 2024, AFTER_SEASON)

    assert stats.sessions_synced == 5
    assert store.table_counts()["session_results"] == 0


def test_sync_counts_rejected_records_below_threshold(load_fixture, store):
    laps = load_fixture("laps")
    laps.extend({**laps[0], "lap_number": n} for n in range(10, 20))
    laps.append({**laps[0], "lap_number": None})
    client = FakeOpenF1Client(load_fixture, {"laps": laps})

    stats = sync_year(client, store, 2024, AFTER_SEASON)

    assert stats.rows_rejected == 1


def test_sync_fails_when_too_many_records_are_rejected(load_fixture, store):
    stints = [{**s, "stint_number": None} for s in load_fixture("stints")]
    client = FakeOpenF1Client(load_fixture, {"stints": stints})

    with pytest.raises(SyncError, match="stints .* rejeitados"):
        sync_year(client, store, 2024, AFTER_SEASON)


def test_sync_session_loads_one_session_and_its_meeting(client, store):
    stats = sync_session(client, store, 9655, AFTER_SEASON)

    assert stats.sessions_synced == 1
    assert store.session(9655) is not None
    assert store.table_counts()["meetings"] == 1
    assert len(store.drivers(9655)) == 5
    assert store.drivers(9646) == []


def test_sync_session_skips_unfinished_session(client, store):
    stats = sync_session(client, store, 9655, DURING_WEEKEND)

    assert stats.sessions_skipped == 1
    assert store.laps(9655) == []


def test_sync_session_fails_for_unknown_session(client, store):
    with pytest.raises(SyncError, match="sessão 1 não encontrada"):
        sync_session(client, store, 1, AFTER_SEASON)
