"""Cliente HTTP da OpenF1 API."""

import logging
import random
import re
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

type FilterScalar = str | int | float | bool | date | datetime
type FilterValue = FilterScalar | Sequence[FilterScalar]

_ENDPOINT = re.compile(r"^[a-z_]+$")
_FILTER_KEY = re.compile(r"^(?P<field>[a-z0-9_]+)(?P<op>>=|<=|>|<)?$")
_NO_RESULTS = "No results found."
_MAX_DELAY_S = 60.0


class OpenF1Error(RuntimeError):
    """A OpenF1 API falhou ou devolveu uma resposta inesperada."""


def build_query(filters: Mapping[str, FilterValue]) -> str:
    """Monta a query string da OpenF1, incluindo filtros com operadores.

    A chave pode terminar em um operador (`"date_start>="`, `"position<"`); sem operador,
    o filtro é de igualdade. Valores em sequência viram parâmetros repetidos.

    Args:
        filters: Filtros por campo.

    Returns:
        Query string sem o `?` inicial.

    Raises:
        ValueError: Se uma chave não for um nome de campo válido.
    """
    parts: list[str] = []
    for key, value in filters.items():
        match = _FILTER_KEY.match(key)
        if match is None:
            raise ValueError(f"filtro inválido: {key!r}")
        operator = match["op"] or "="
        values = value if isinstance(value, Sequence) and not isinstance(value, str) else [value]
        parts.extend(
            f"{match['field']}{operator}{quote(_format_value(item), safe='')}" for item in values
        )
    return "&".join(parts)


def _format_value(value: FilterScalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


class OpenF1Client:
    """Cliente da OpenF1 com timeout, retry para erros transitórios e intervalo mínimo.

    Use como context manager para fechar a conexão HTTP ao final.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float,
        min_interval_s: float = 0.5,
        max_attempts: int = 5,
        backoff_base_s: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts precisa ser >= 1")
        self._http = httpx.Client(base_url=base_url, timeout=timeout_s, transport=transport)
        self._min_interval_s = min_interval_s
        self._max_attempts = max_attempts
        self._backoff_base_s = backoff_base_s
        self._sleep = sleep
        self._clock = clock
        self._jitter = jitter
        self._last_request_at: float | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Fecha a conexão HTTP."""
        self._http.close()

    def get(
        self, endpoint: str, filters: Mapping[str, FilterValue] | None = None
    ) -> list[dict[str, Any]]:
        """Consulta um endpoint e devolve os registros.

        Uma consulta sem resultados (a API responde 404 "No results found.") devolve lista vazia.

        Args:
            endpoint: Nome do endpoint, por exemplo `"sessions"`.
            filters: Filtros da consulta (ver `build_query`).

        Returns:
            Registros devolvidos pela API.

        Raises:
            ValueError: Se o endpoint ou um filtro for inválido.
            OpenF1Error: Se a API falhar após as tentativas ou responder com erro não transitório.
        """
        if _ENDPOINT.match(endpoint) is None:
            raise ValueError(f"endpoint inválido: {endpoint!r}")
        query = build_query(filters or {})
        url = f"/{endpoint}?{query}" if query else f"/{endpoint}"

        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            try:
                response = self._http.get(url)
            except httpx.TimeoutException as exc:
                if attempt == self._max_attempts:
                    raise OpenF1Error(f"timeout em {url} após {attempt} tentativas") from exc
                self._backoff(attempt, url, "timeout", retry_after=None)
                continue

            status = response.status_code
            if status == 429 or status >= 500:
                if attempt == self._max_attempts:
                    raise OpenF1Error(f"HTTP {status} em {url} após {attempt} tentativas")
                self._backoff(attempt, url, f"HTTP {status}", _retry_after(response))
                continue
            return _parse_response(response, url)

    def _throttle(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            wait = self._min_interval_s - (now - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_request_at = now

    def _backoff(self, attempt: int, url: str, reason: str, retry_after: float | None) -> None:
        delay = self._backoff_base_s * 2 ** (attempt - 1) + self._jitter() * self._backoff_base_s
        if retry_after is not None:
            delay = max(delay, retry_after)
        delay = min(delay, _MAX_DELAY_S)
        logger.warning(
            "%s em %s; nova tentativa %d/%d em %.1fs",
            reason,
            url,
            attempt + 1,
            self._max_attempts,
            delay,
        )
        self._sleep(delay)


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_response(response: httpx.Response, url: str) -> list[dict[str, Any]]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenF1Error(f"resposta não é JSON em {url} (HTTP {response.status_code})") from exc

    # A OpenF1 responde 404 para consultas sem resultado; isso não é erro.
    if (
        response.status_code == 404
        and isinstance(payload, dict)
        and payload.get("detail") == _NO_RESULTS
    ):
        return []
    if response.is_error:
        raise OpenF1Error(f"HTTP {response.status_code} em {url}: {payload}")
    if not isinstance(payload, list):
        raise OpenF1Error(
            f"resposta inesperada em {url}: esperava lista, veio {type(payload).__name__}"
        )
    return payload
