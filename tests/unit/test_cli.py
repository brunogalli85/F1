import logging
from datetime import UTC, datetime

import httpx
import pytest

from f1 import __main__ as entrypoint
from f1 import cli
from f1.config import Settings
from f1.domain.parsing import (
    parse_driver,
    parse_lap,
    parse_pit_stop,
    parse_session,
    parse_session_result,
    parse_stint,
)
from f1.infrastructure.duckdb_store import DuckDbStore


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=tmp_path / "f1.duckdb", min_request_interval_s=0.0)


@pytest.fixture
def populated(settings, load_fixture):
    with DuckDbStore(settings.db_path) as db:
        db.upsert([parse_session(r) for r in load_fixture("sessions")])
        db.upsert([parse_driver(r) for r in load_fixture("drivers")])
        db.upsert([parse_driver({**r, "session_key": 9646}) for r in load_fixture("drivers")])
        db.upsert([parse_session_result(r) for r in load_fixture("session_result_race")])
        db.upsert([parse_session_result(r) for r in load_fixture("session_result_qualifying")])
        db.upsert([parse_lap(r) for r in load_fixture("laps")])
        db.upsert([parse_stint(r) for r in load_fixture("stints")])
        db.upsert([parse_pit_stop(r) for r in load_fixture("pit")])
    return settings


def run(capsys, settings, *argv):
    code = cli.main(list(argv), settings)
    return code, capsys.readouterr().out


def test_sessions_lists_cached_sessions(capsys, populated):
    code, out = run(capsys, populated, "sessions", "--year", "2024", "--country", "Qatar")

    assert code == 0
    assert "9655" in out and "Sprint Qualifying" in out and "Lusail" in out


def test_sessions_with_empty_cache(capsys, settings):
    code, out = run(capsys, settings, "sessions")

    assert code == 0
    assert "Nenhuma sessão no cache" in out


def test_results_for_race(capsys, populated):
    code, out = run(capsys, populated, "results", "--session-key", "9655")

    lines = out.splitlines()
    assert code == 0
    assert lines[0].startswith("Qatar 2024 - Race (2024-12-01")
    assert "1:31:05.323" in out  # tempo total do vencedor
    assert "+6.031s" in out
    assert "+1 volta" in out
    assert lines[-1].split()[:3] == ["-", "18", "STR"]
    assert "DNF" in lines[-1]


def test_results_for_qualifying_shows_phases(capsys, populated):
    code, out = run(capsys, populated, "results", "--session-key", "9646")

    assert code == 0
    assert "Q3" in out
    assert "1:20.520" in out


def test_results_without_data(capsys, populated):
    code, out = run(capsys, populated, "results", "--session-key", "9645")

    assert code == 0
    assert "Sem resultado" in out


def test_fastest_laps_with_top(capsys, populated):
    code, out = run(capsys, populated, "fastest-laps", "--session-key", "9655", "--top", "1")

    assert code == 0
    assert "VER" in out and "1:51.736" in out
    assert "LEC" not in out


def test_strategy_follows_finishing_order(capsys, populated):
    code, out = run(capsys, populated, "strategy", "--session-key", "9655")

    assert code == 0
    assert "MEDIUM(35) > HARD(1) > HARD(1) > HARD(20)" in out
    assert out.index("VER") < out.index("LEC")


def test_pits_summary(capsys, populated):
    code, out = run(capsys, populated, "pits", "--session-key", "9655")

    assert code == 0
    assert "35, 36, 37" in out
    assert "2.5s" in out


@pytest.mark.parametrize("command", ["fastest-laps", "strategy", "pits"])
def test_reports_for_session_without_data(capsys, populated, command):
    code, out = run(capsys, populated, command, "--session-key", "9645")

    assert code == 0
    assert out.splitlines()[-1].startswith("Sem ")


def test_report_for_unknown_session_raises_cli_error(populated):
    with pytest.raises(cli.CliError, match="f1 sync --session-key 1"):
        cli.main(["results", "--session-key", "1"], populated)


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["sync"],
        ["sync", "--year", "2024", "--session-key", "1"],
        ["fastest-laps", "--session-key", "1", "--top", "0"],
    ],
)
def test_invalid_arguments_exit_with_usage_error(settings, argv):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv, settings)
    assert excinfo.value.code == 2


def test_sync_command_uses_the_api(capsys, settings, load_fixture, monkeypatch):
    responses = {
        "sessions": [load_fixture("sessions")[-1]],
        "meetings": load_fixture("meetings"),
        "drivers": load_fixture("drivers"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        if endpoint in responses:
            return httpx.Response(200, json=responses[endpoint])
        return httpx.Response(404, json={"detail": "No results found."})

    real_client = httpx.Client

    def client_with_mock_transport(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    monkeypatch.setattr(httpx, "Client", client_with_mock_transport)

    code = cli.main(
        ["sync", "--session-key", "9655"], settings, now=datetime(2025, 1, 1, tzinfo=UTC)
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "Sessões sincronizadas: 1" in out
    with DuckDbStore(settings.db_path) as db:
        assert len(db.drivers(9655)) == 5


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(None, "-"), (80.52, "1:20.520"), (59.9999, "1:00.000"), (5465.323, "1:31:05.323")],
)
def test_format_seconds(seconds, expected):
    assert cli.format_seconds(seconds) == expected


def test_format_table_aligns_columns():
    table = cli.format_table(["A", "Longo"], [["xyz", 1]])

    assert table.splitlines() == ["A    Longo", "---  -----", "xyz  1"]


# ── entrypoint ────────────────────────────────────────────────────────────


def test_entrypoint_returns_zero_on_success(monkeypatch):
    monkeypatch.setattr(cli, "main", lambda argv: 0)

    assert entrypoint.main([]) == 0


@pytest.mark.parametrize(
    "error",
    [cli.CliError("sessão não está no cache"), ValueError("HTTP_TIMEOUT_S inválido")],
)
def test_entrypoint_turns_known_errors_into_exit_code(monkeypatch, caplog, error):
    def fail(argv):
        raise error

    monkeypatch.setattr(cli, "main", fail)

    with caplog.at_level(logging.ERROR):
        assert entrypoint.main([]) == 1
    assert str(error) in caplog.text
    assert "Traceback" not in caplog.text


def test_entrypoint_logs_traceback_for_unexpected_errors(monkeypatch, caplog):
    def fail(argv):
        raise KeyError("bug")

    monkeypatch.setattr(cli, "main", fail)

    with caplog.at_level(logging.ERROR):
        assert entrypoint.main([]) == 1
    assert "erro inesperado" in caplog.text
    assert caplog.records[-1].exc_info is not None
