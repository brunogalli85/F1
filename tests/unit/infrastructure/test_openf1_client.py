from datetime import date

import httpx
import pytest

from f1.infrastructure.openf1_client import OpenF1Client, OpenF1Error, build_query

BASE_URL = "https://api.test/v1"


class FakeClock:
    """Relógio controlado: `sleep` avança o tempo em vez de esperar."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, clock: FakeClock | None = None, **kwargs) -> OpenF1Client:
    clock = clock or FakeClock()
    return OpenF1Client(
        BASE_URL,
        timeout_s=1.0,
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock,
        jitter=lambda: 0.0,
        **kwargs,
    )


def test_build_query_supports_operators_repeated_values_and_encoding():
    query = build_query(
        {
            "session_key": 9655,
            "lap_number>=": 10,
            "lap_number<": 20,
            "driver_number": [1, 16],
            "session_name": "Sprint Qualifying",
            "is_cancelled": False,
            "date_start>": date(2024, 12, 1),
        }
    )

    assert query == (
        "session_key=9655&lap_number>=10&lap_number<20&driver_number=1&driver_number=16"
        "&session_name=Sprint%20Qualifying&is_cancelled=false&date_start>2024-12-01"
    )


@pytest.mark.parametrize("key", ["speed>>", "Speed", "speed=", ""])
def test_build_query_rejects_invalid_keys(key):
    with pytest.raises(ValueError, match="filtro inválido"):
        build_query({key: 1})


def test_get_sends_operator_filters_and_returns_records():
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json=[{"session_key": 9655}])

    with make_client(handler) as client:
        records = client.get("laps", {"session_key": 9655, "lap_number>=": 10})

    assert records == [{"session_key": 9655}]
    assert seen[0].path == "/v1/laps"
    assert httpx.QueryParams(seen[0].query.decode()).get("lap_number>") == "10"


def test_get_without_filters_has_no_query_string():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.query == b""
        return httpx.Response(200, json=[])

    with make_client(handler) as client:
        assert client.get("meetings") == []


def test_get_returns_empty_list_for_no_results_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "No results found."})

    with make_client(handler) as client:
        assert client.get("session_result", {"session_key": 1}) == []


def test_get_does_not_retry_other_404():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(404, json={"detail": "Not Found"})

    with make_client(handler) as client, pytest.raises(OpenF1Error, match="HTTP 404"):
        client.get("unknown_endpoint")
    assert len(calls) == 1


@pytest.mark.parametrize("status", [429, 500, 503])
def test_get_retries_transient_errors_with_exponential_backoff(status):
    responses = iter(
        [httpx.Response(status), httpx.Response(status), httpx.Response(200, json=[{"a": 1}])]
    )
    clock = FakeClock()

    with make_client(lambda request: next(responses), clock, min_interval_s=0.0) as client:
        assert client.get("sessions") == [{"a": 1}]
    assert clock.sleeps == [1.0, 2.0]


def test_get_honors_retry_after_header():
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=[])]
    )
    clock = FakeClock()

    with make_client(lambda request: next(responses), clock, min_interval_s=0.0) as client:
        client.get("sessions")
    assert clock.sleeps == [7.0]


def test_get_fails_after_max_attempts():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(502)

    with (
        make_client(handler, max_attempts=3, min_interval_s=0.0) as client,
        pytest.raises(OpenF1Error, match="HTTP 502 .* após 3 tentativas"),
    ):
        client.get("sessions")
    assert len(calls) == 3


def test_get_retries_timeouts_and_wraps_the_last_one():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento", request=request)

    with (
        make_client(handler, max_attempts=2, min_interval_s=0.0) as client,
        pytest.raises(OpenF1Error, match="timeout") as excinfo,
    ):
        client.get("sessions")
    assert isinstance(excinfo.value.__cause__, httpx.ReadTimeout)


def test_get_does_not_retry_client_errors():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(422, json={"detail": "invalid"})

    with make_client(handler) as client, pytest.raises(OpenF1Error, match="HTTP 422"):
        client.get("sessions", {"year": "abc"})
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, text="<html>"), "não é JSON"),
        (httpx.Response(200, json={"detail": "x"}), "esperava lista"),
    ],
)
def test_get_rejects_unexpected_payloads(response, message):
    with make_client(lambda request: response) as client, pytest.raises(OpenF1Error, match=message):
        client.get("sessions")


def test_get_waits_min_interval_between_requests():
    clock = FakeClock()

    with make_client(
        lambda request: httpx.Response(200, json=[]), clock, min_interval_s=0.5
    ) as client:
        client.get("sessions")
        clock.now += 0.2
        client.get("sessions")
        clock.now += 1.0
        client.get("sessions")

    assert clock.sleeps == [pytest.approx(0.3)]


def test_get_rejects_invalid_endpoint():
    with (
        make_client(lambda request: httpx.Response(200, json=[])) as client,
        pytest.raises(ValueError, match="endpoint inválido"),
    ):
        client.get("../admin")


def test_client_rejects_invalid_max_attempts():
    with pytest.raises(ValueError, match="max_attempts"):
        OpenF1Client(BASE_URL, timeout_s=1.0, max_attempts=0)
