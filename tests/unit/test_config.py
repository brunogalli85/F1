from pathlib import Path

import pytest

from f1.config import DEFAULT_BASE_URL, Settings


def test_from_env_uses_defaults_when_variables_are_missing():
    settings = Settings.from_env({})

    assert settings == Settings(
        openf1_base_url=DEFAULT_BASE_URL,
        db_path=Path("data/f1.duckdb"),
        http_timeout_s=30.0,
        min_request_interval_s=0.5,
    )


def test_from_env_reads_all_variables():
    settings = Settings.from_env(
        {
            "OPENF1_BASE_URL": "http://localhost:8000/v1",
            "F1_DB_PATH": "/tmp/x.duckdb",
            "HTTP_TIMEOUT_S": "5",
            "OPENF1_MIN_INTERVAL_S": "0",
        }
    )

    assert settings.openf1_base_url == "http://localhost:8000/v1"
    assert settings.db_path == Path("/tmp/x.duckdb")
    assert settings.http_timeout_s == 5.0
    assert settings.min_request_interval_s == 0.0


def test_from_env_treats_empty_values_as_missing():
    assert Settings.from_env({"HTTP_TIMEOUT_S": "", "F1_DB_PATH": ""}) == Settings()


def test_from_env_reads_os_environ_by_default(monkeypatch):
    monkeypatch.setenv("HTTP_TIMEOUT_S", "12")

    assert Settings.from_env().http_timeout_s == 12.0


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"HTTP_TIMEOUT_S": "abc"}, "HTTP_TIMEOUT_S precisa ser um número"),
        ({"HTTP_TIMEOUT_S": "0"}, r"HTTP_TIMEOUT_S precisa ser > 0"),
        ({"OPENF1_MIN_INTERVAL_S": "-1"}, r"OPENF1_MIN_INTERVAL_S precisa ser >= 0"),
    ],
)
def test_from_env_rejects_invalid_values(env, message):
    with pytest.raises(ValueError, match=message):
        Settings.from_env(env)
