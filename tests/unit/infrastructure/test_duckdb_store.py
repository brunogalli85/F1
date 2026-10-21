from dataclasses import replace
from datetime import UTC, datetime

import pytest

from f1.domain.models import SyncRun
from f1.domain.parsing import (
    parse_driver,
    parse_lap,
    parse_meeting,
    parse_pit_stop,
    parse_session,
    parse_session_result,
    parse_stint,
)
from f1.infrastructure.duckdb_store import DuckDbStore


@pytest.fixture
def sessions(load_fixture):
    return [parse_session(r) for r in load_fixture("sessions")]


def test_new_store_has_empty_schema(store):
    assert set(store.table_counts().values()) == {0}
    assert store.sessions() == []
    assert store.session(9655) is None


def test_upsert_and_read_back_sessions_with_utc_dates(store, sessions):
    assert store.upsert(sessions) == 5

    race = store.session(9655)

    assert race == next(s for s in sessions if s.session_key == 9655)
    assert race.date_start.tzinfo == UTC


def test_upsert_is_idempotent_and_updates_existing_rows(store, sessions):
    store.upsert(sessions)
    renamed = replace(sessions[0], session_name="Practice 1 (renomeada)")

    store.upsert([renamed, *sessions[1:]])

    assert store.table_counts()["sessions"] == 5
    assert store.session(renamed.session_key).session_name == "Practice 1 (renomeada)"


def test_upsert_keeps_last_duplicate_in_batch(store, sessions):
    first = sessions[0]
    duplicate = replace(first, session_name="última")

    assert store.upsert([first, duplicate]) == 1
    assert store.session(first.session_key).session_name == "última"


def test_upsert_of_empty_batch(store):
    assert store.upsert([]) == 0


def test_upsert_rejects_mixed_record_types(store, sessions, load_fixture):
    meeting = parse_meeting(load_fixture("meetings")[0])

    with pytest.raises(TypeError, match="único tipo"):
        store.upsert([sessions[0], meeting])


def test_upsert_large_batch(store, load_fixture):
    template = parse_lap(load_fixture("laps")[0])
    laps = [replace(template, lap_number=n) for n in range(1, 1201)]

    assert store.upsert(laps) == 1200
    assert len(store.laps(template.session_key)) == 1200


def test_upsert_preserves_quotes_unicode_and_nulls(store, load_fixture):
    driver = replace(
        parse_driver(load_fixture("drivers")[0]), full_name="Sergio 'Checo' Pérez", team_name=None
    )

    store.upsert([driver])

    assert store.drivers(driver.session_key) == [driver]


def test_sessions_filters_by_year_and_country_case_insensitive(store, sessions):
    other = replace(sessions[0], session_key=1, year=2023, country_name="Belgium")
    store.upsert([*sessions, other])

    assert [s.session_key for s in store.sessions(year=2023)] == [1]
    assert len(store.sessions(country="qatar")) == 5
    assert store.sessions(year=2023, country="Qatar") == []
    keys = [s.session_key for s in store.sessions(year=2024)]
    assert keys == [9645, 9650, 9654, 9646, 9655]  # cronológica: o sprint vem antes da quali


def test_session_scoped_reads_return_only_that_session(store, load_fixture):
    store.upsert([parse_driver(r) for r in load_fixture("drivers")])
    store.upsert([parse_session_result(r) for r in load_fixture("session_result_race")])
    store.upsert([parse_session_result(r) for r in load_fixture("session_result_qualifying")])
    store.upsert([parse_lap(r) for r in load_fixture("laps")])
    store.upsert([parse_stint(r) for r in load_fixture("stints")])
    store.upsert([parse_pit_stop(r) for r in load_fixture("pit")])

    assert len(store.drivers(9655)) == 5
    assert len(store.session_results(9655)) == 5
    assert [r.q3 for r in store.session_results(9646)][:1] == [80.52]
    assert [(lap.driver_number, lap.lap_number) for lap in store.laps(9655)][:2] == [(1, 1), (1, 2)]
    assert len(store.stints(9655)) == 8
    assert store.pit_stops(9655)[0].date.tzinfo == UTC
    assert store.laps(1) == []


def test_transaction_rolls_back_on_error(store, sessions):
    with pytest.raises(RuntimeError, match="falhou"), store.transaction():
        store.upsert(sessions)
        raise RuntimeError("falhou")

    assert store.table_counts()["sessions"] == 0


def test_transaction_commits(store, sessions):
    with store.transaction():
        store.upsert(sessions)

    assert store.table_counts()["sessions"] == 5


def test_records_sync_run(store):
    now = datetime(2024, 12, 2, tzinfo=UTC)
    store.upsert([SyncRun("abc", "year=2024", now, now, 1, 0, 10, 9, 1)])

    assert store.table_counts()["sync_runs"] == 1


def test_file_store_persists_between_connections(tmp_path, sessions):
    path = tmp_path / "nested" / "f1.duckdb"

    with DuckDbStore(path) as db:
        db.upsert(sessions)
    with DuckDbStore(path) as db:
        assert len(db.sessions()) == 5
