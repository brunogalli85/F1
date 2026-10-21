"""Entidades do domínio, uma por endpoint da OpenF1 usado no MVP.

Os nomes dos campos são os mesmos das colunas no DuckDB. Datas são `datetime` em UTC.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Meeting:
    """Fim de semana de GP ou teste."""

    meeting_key: int
    year: int
    meeting_name: str
    meeting_official_name: str | None
    country_name: str | None
    location: str | None
    circuit_short_name: str | None
    circuit_type: str | None
    gmt_offset: str | None
    date_start: datetime | None
    date_end: datetime | None
    is_cancelled: bool


@dataclass(frozen=True, slots=True)
class Session:
    """Sessão de um meeting (treino, classificação, sprint, corrida)."""

    session_key: int
    meeting_key: int
    year: int
    session_type: str
    session_name: str
    country_name: str | None
    location: str | None
    circuit_short_name: str | None
    date_start: datetime
    date_end: datetime | None
    is_cancelled: bool


@dataclass(frozen=True, slots=True)
class Driver:
    """Piloto inscrito em uma sessão."""

    session_key: int
    driver_number: int
    meeting_key: int | None
    full_name: str | None
    broadcast_name: str | None
    first_name: str | None
    last_name: str | None
    name_acronym: str | None
    team_name: str | None
    team_colour: str | None
    headshot_url: str | None


@dataclass(frozen=True, slots=True)
class SessionResult:
    """Resultado final de um piloto em uma sessão.

    Em corrida, `duration` é o tempo total e `gap_to_leader` a diferença em segundos;
    quem tomou volta tem `laps_behind` preenchido e `gap_to_leader` nulo. Em classificação,
    os tempos de cada fase ficam em `q1`/`q2`/`q3`, e `gap_to_leader` é o da última fase
    disputada pelo piloto.
    """

    session_key: int
    driver_number: int
    meeting_key: int | None
    position: int | None
    number_of_laps: int | None
    points: float | None
    dnf: bool
    dns: bool
    dsq: bool
    duration: float | None
    gap_to_leader: float | None
    laps_behind: int | None
    q1: float | None
    q2: float | None
    q3: float | None


@dataclass(frozen=True, slots=True)
class Lap:
    """Volta de um piloto."""

    session_key: int
    driver_number: int
    lap_number: int
    meeting_key: int | None
    date_start: datetime | None
    lap_duration: float | None
    duration_sector_1: float | None
    duration_sector_2: float | None
    duration_sector_3: float | None
    i1_speed: int | None
    i2_speed: int | None
    st_speed: int | None
    is_pit_out_lap: bool


@dataclass(frozen=True, slots=True)
class Stint:
    """Período contínuo com o mesmo jogo de pneus."""

    session_key: int
    driver_number: int
    stint_number: int
    meeting_key: int | None
    compound: str | None
    lap_start: int | None
    lap_end: int | None
    tyre_age_at_start: int | None


@dataclass(frozen=True, slots=True)
class SyncRun:
    """Registro de uma execução de sincronização, para observabilidade."""

    run_id: str
    scope: str
    started_at: datetime
    finished_at: datetime
    sessions_synced: int
    sessions_skipped: int
    rows_read: int
    rows_written: int
    rows_rejected: int


@dataclass(frozen=True, slots=True)
class PitStop:
    """Passagem pelo pit lane."""

    session_key: int
    driver_number: int
    lap_number: int
    meeting_key: int | None
    date: datetime | None
    lane_duration: float | None
    stop_duration: float | None
