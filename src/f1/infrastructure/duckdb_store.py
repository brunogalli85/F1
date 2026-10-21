"""Cache local dos dados da OpenF1 em DuckDB."""

import json
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import duckdb

from f1.domain.models import Driver, Lap, Meeting, PitStop, Session, SessionResult, Stint, SyncRun

logger = logging.getLogger(__name__)

type Record = Meeting | Session | Driver | SessionResult | Lap | Stint | PitStop | SyncRun


@dataclass(frozen=True, slots=True)
class _Table:
    name: str
    key: tuple[str, ...]


_TABLES: dict[type, _Table] = {
    Meeting: _Table("meetings", ("meeting_key",)),
    Session: _Table("sessions", ("session_key",)),
    Driver: _Table("drivers", ("session_key", "driver_number")),
    SessionResult: _Table("session_results", ("session_key", "driver_number")),
    Lap: _Table("laps", ("session_key", "driver_number", "lap_number")),
    Stint: _Table("stints", ("session_key", "driver_number", "stint_number")),
    PitStop: _Table("pit_stops", ("session_key", "driver_number", "lap_number")),
    SyncRun: _Table("sync_runs", ("run_id",)),
}

# Datas ficam em TIMESTAMP (UTC, sem fuso): TIMESTAMPTZ exigiria pytz para voltar ao Python.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    meeting_key INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    meeting_name VARCHAR NOT NULL,
    meeting_official_name VARCHAR,
    country_name VARCHAR,
    location VARCHAR,
    circuit_short_name VARCHAR,
    circuit_type VARCHAR,
    gmt_offset VARCHAR,
    date_start TIMESTAMP,
    date_end TIMESTAMP,
    is_cancelled BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    session_key INTEGER PRIMARY KEY,
    meeting_key INTEGER NOT NULL,
    year INTEGER NOT NULL,
    session_type VARCHAR NOT NULL,
    session_name VARCHAR NOT NULL,
    country_name VARCHAR,
    location VARCHAR,
    circuit_short_name VARCHAR,
    date_start TIMESTAMP NOT NULL,
    date_end TIMESTAMP,
    is_cancelled BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS drivers (
    session_key INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    meeting_key INTEGER,
    full_name VARCHAR,
    broadcast_name VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    name_acronym VARCHAR,
    team_name VARCHAR,
    team_colour VARCHAR,
    headshot_url VARCHAR,
    PRIMARY KEY (session_key, driver_number)
);
CREATE TABLE IF NOT EXISTS session_results (
    session_key INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    meeting_key INTEGER,
    position INTEGER,
    number_of_laps INTEGER,
    points DOUBLE,
    dnf BOOLEAN NOT NULL,
    dns BOOLEAN NOT NULL,
    dsq BOOLEAN NOT NULL,
    duration DOUBLE,
    gap_to_leader DOUBLE,
    laps_behind INTEGER,
    q1 DOUBLE,
    q2 DOUBLE,
    q3 DOUBLE,
    PRIMARY KEY (session_key, driver_number)
);
CREATE TABLE IF NOT EXISTS laps (
    session_key INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    lap_number INTEGER NOT NULL,
    meeting_key INTEGER,
    date_start TIMESTAMP,
    lap_duration DOUBLE,
    duration_sector_1 DOUBLE,
    duration_sector_2 DOUBLE,
    duration_sector_3 DOUBLE,
    i1_speed INTEGER,
    i2_speed INTEGER,
    st_speed INTEGER,
    is_pit_out_lap BOOLEAN NOT NULL,
    PRIMARY KEY (session_key, driver_number, lap_number)
);
CREATE TABLE IF NOT EXISTS stints (
    session_key INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    stint_number INTEGER NOT NULL,
    meeting_key INTEGER,
    compound VARCHAR,
    lap_start INTEGER,
    lap_end INTEGER,
    tyre_age_at_start INTEGER,
    PRIMARY KEY (session_key, driver_number, stint_number)
);
CREATE TABLE IF NOT EXISTS pit_stops (
    session_key INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    lap_number INTEGER NOT NULL,
    meeting_key INTEGER,
    date TIMESTAMP,
    lane_duration DOUBLE,
    stop_duration DOUBLE,
    PRIMARY KEY (session_key, driver_number, lap_number)
);
CREATE TABLE IF NOT EXISTS sync_runs (
    run_id VARCHAR PRIMARY KEY,
    scope VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NOT NULL,
    sessions_synced INTEGER NOT NULL,
    sessions_skipped INTEGER NOT NULL,
    rows_read INTEGER NOT NULL,
    rows_written INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL
);
"""


class DuckDbStore:
    """Leitura e gravação idempotente (upsert por chave natural) no DuckDB.

    Use como context manager para fechar a conexão ao final.
    """

    def __init__(self, path: Path | str) -> None:
        """Abre (ou cria) o banco e garante o schema.

        Args:
            path: Arquivo do banco, ou `":memory:"` para um banco em memória.
        """
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(path))
        self._conn.execute(_SCHEMA)
        self._row_types = {table.name: self._row_type(table.name) for table in _TABLES.values()}

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
        """Fecha a conexão."""
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Executa o bloco em uma transação: commit ao final, rollback em caso de erro."""
        self._conn.begin()
        try:
            yield
        except BaseException:
            self._conn.rollback()
            raise
        self._conn.commit()

    def upsert(self, records: Sequence[Record]) -> int:
        """Insere ou atualiza registros de um mesmo tipo pela chave natural.

        Registros repetidos no lote (mesma chave) ficam com a última ocorrência.

        Args:
            records: Registros de um único tipo do domínio.

        Returns:
            Número de linhas gravadas.

        Raises:
            TypeError: Se os registros forem de tipos diferentes ou não mapeados.
        """
        if not records:
            return 0
        model = type(records[0])
        table = _TABLES.get(model)
        if table is None or any(type(r) is not model for r in records):
            raise TypeError(f"upsert exige registros de um único tipo mapeado, veio {model}")

        columns = [f.name for f in fields(model)]
        # O DuckDB não aceita a mesma chave duas vezes em um único ON CONFLICT DO UPDATE.
        unique: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            row = {name: _to_json(getattr(record, name)) for name in columns}
            unique[tuple(row[k] for k in table.key)] = row

        # O lote vai como um único parâmetro JSON, convertido pelo próprio DuckDB:
        # converter valor a valor a partir do Python custa ~0,3 ms por campo.
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c not in table.key)
        sql = (
            f"INSERT INTO {table.name} BY NAME "
            f"SELECT unnest(from_json(?, '{self._row_types[table.name]}'), recursive := true) "
            f"ON CONFLICT ({', '.join(table.key)}) DO UPDATE SET {updates}"
        )
        self._conn.execute(sql, [json.dumps(list(unique.values()))])
        logger.debug("upsert de %d linhas em %s", len(unique), table.name)
        return len(unique)

    def table_counts(self) -> dict[str, int]:
        """Número de linhas por tabela."""
        return {
            table.name: self._conn.execute(f"SELECT count(*) FROM {table.name}").fetchone()[0]
            for table in _TABLES.values()
        }

    def sessions(self, year: int | None = None, country: str | None = None) -> list[Session]:
        """Lista as sessões gravadas, em ordem cronológica.

        Args:
            year: Filtra pela temporada.
            country: Filtra pelo país (sem diferenciar maiúsculas e minúsculas).
        """
        conditions = []
        params: list[Any] = []
        if year is not None:
            conditions.append("year = ?")
            params.append(year)
        if country is not None:
            conditions.append("lower(country_name) = lower(?)")
            params.append(country)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self._select(Session, f"SELECT * FROM sessions {where} ORDER BY date_start", params)

    def session(self, session_key: int) -> Session | None:
        """Busca uma sessão pela chave."""
        found = self._select(Session, "SELECT * FROM sessions WHERE session_key = ?", [session_key])
        return found[0] if found else None

    def drivers(self, session_key: int) -> list[Driver]:
        """Pilotos de uma sessão."""
        return self._select_session_rows(Driver, session_key, "driver_number")

    def session_results(self, session_key: int) -> list[SessionResult]:
        """Resultados de uma sessão."""
        return self._select_session_rows(SessionResult, session_key, "driver_number")

    def laps(self, session_key: int) -> list[Lap]:
        """Voltas de uma sessão."""
        return self._select_session_rows(Lap, session_key, "driver_number, lap_number")

    def stints(self, session_key: int) -> list[Stint]:
        """Stints de uma sessão."""
        return self._select_session_rows(Stint, session_key, "driver_number, stint_number")

    def pit_stops(self, session_key: int) -> list[PitStop]:
        """Pit stops de uma sessão."""
        return self._select_session_rows(PitStop, session_key, "driver_number, lap_number")

    def _row_type(self, table: str) -> str:
        """Tipo `from_json` de uma lista de linhas da tabela, derivado do schema criado."""
        columns = self._conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        return json.dumps([dict(columns)])

    def _select_session_rows[T](self, model: type[T], session_key: int, order_by: str) -> list[T]:
        table = _TABLES[model].name
        sql = f"SELECT * FROM {table} WHERE session_key = ? ORDER BY {order_by}"
        return self._select(model, sql, [session_key])

    def _select[T](self, model: type[T], sql: str, params: Sequence[Any]) -> list[T]:
        cursor = self._conn.execute(sql, list(params))
        names = [column[0] for column in cursor.description]
        return [
            model(**{name: _from_db(value) for name, value in zip(names, row, strict=True)})
            for row in cursor.fetchall()
        ]


def _to_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(tzinfo=None).isoformat()
    return value


def _from_db(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
