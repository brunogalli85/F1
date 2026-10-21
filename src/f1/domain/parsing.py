"""Conversão dos registros da OpenF1 (dicts) em entidades do domínio."""

import logging
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from f1.domain.models import Driver, Lap, Meeting, PitStop, Session, SessionResult, Stint

logger = logging.getLogger(__name__)

type RawRecord = Mapping[str, Any]

_LAPS_BEHIND = re.compile(r"^\+(\d+) LAPS?$")


class InvalidRecordError(ValueError):
    """Registro da API sem um campo obrigatório ou com tipo inesperado."""


@dataclass(frozen=True, slots=True)
class ParseResult[T]:
    """Registros válidos de um lote e a contagem de rejeitados."""

    records: list[T]
    rejected: int


def parse_many[T](raws: Iterable[RawRecord], parser: Callable[[RawRecord], T]) -> ParseResult[T]:
    """Aplica `parser` a cada registro; registros inválidos são contados, não derrubam o lote.

    Args:
        raws: Registros brutos da API.
        parser: Uma das funções `parse_*` deste módulo.

    Returns:
        Registros válidos e número de rejeitados.
    """
    records: list[T] = []
    rejected = 0
    for raw in raws:
        try:
            records.append(parser(raw))
        except InvalidRecordError as exc:
            rejected += 1
            logger.warning("registro rejeitado por %s: %s", parser.__name__, exc)
    return ParseResult(records, rejected)


def parse_meeting(raw: RawRecord) -> Meeting:
    """Converte um registro de `meetings`."""
    return Meeting(
        meeting_key=_int(raw, "meeting_key"),
        year=_int(raw, "year"),
        meeting_name=_str(raw, "meeting_name"),
        meeting_official_name=_opt_str(raw, "meeting_official_name"),
        country_name=_opt_str(raw, "country_name"),
        location=_opt_str(raw, "location"),
        circuit_short_name=_opt_str(raw, "circuit_short_name"),
        circuit_type=_opt_str(raw, "circuit_type"),
        gmt_offset=_opt_str(raw, "gmt_offset"),
        date_start=_opt_datetime(raw, "date_start"),
        date_end=_opt_datetime(raw, "date_end"),
        is_cancelled=_bool(raw, "is_cancelled"),
    )


def parse_session(raw: RawRecord) -> Session:
    """Converte um registro de `sessions`."""
    date_start = _opt_datetime(raw, "date_start")
    if date_start is None:
        raise InvalidRecordError("campo obrigatório ausente: 'date_start'")
    return Session(
        session_key=_int(raw, "session_key"),
        meeting_key=_int(raw, "meeting_key"),
        year=_int(raw, "year"),
        session_type=_str(raw, "session_type"),
        session_name=_str(raw, "session_name"),
        country_name=_opt_str(raw, "country_name"),
        location=_opt_str(raw, "location"),
        circuit_short_name=_opt_str(raw, "circuit_short_name"),
        date_start=date_start,
        date_end=_opt_datetime(raw, "date_end"),
        is_cancelled=_bool(raw, "is_cancelled"),
    )


def parse_driver(raw: RawRecord) -> Driver:
    """Converte um registro de `drivers` (ignora `country_code`, deprecated)."""
    return Driver(
        session_key=_int(raw, "session_key"),
        driver_number=_int(raw, "driver_number"),
        meeting_key=_opt_int(raw, "meeting_key"),
        full_name=_opt_str(raw, "full_name"),
        broadcast_name=_opt_str(raw, "broadcast_name"),
        first_name=_opt_str(raw, "first_name"),
        last_name=_opt_str(raw, "last_name"),
        name_acronym=_opt_str(raw, "name_acronym"),
        team_name=_opt_str(raw, "team_name"),
        team_colour=_opt_str(raw, "team_colour"),
        headshot_url=_opt_str(raw, "headshot_url"),
    )


def parse_session_result(raw: RawRecord) -> SessionResult:
    """Converte um registro de `session_result`.

    Em classificação, `duration` e `gap_to_leader` chegam como arrays [Q1, Q2, Q3].
    Em corrida, `gap_to_leader` pode ser `"+N LAP(S)"`.
    """
    raw_duration = raw.get("duration")
    raw_gap = raw.get("gap_to_leader")
    q1 = q2 = q3 = None
    laps_behind = None

    if isinstance(raw_duration, list):
        q1, q2, q3 = _qualifying_phases(raw_duration, "duration")
        duration = None
    else:
        duration = _opt_float(raw, "duration")

    if isinstance(raw_gap, list):
        phases = [gap for gap in _qualifying_phases(raw_gap, "gap_to_leader") if gap is not None]
        gap_to_leader = phases[-1] if phases else None
    elif isinstance(raw_gap, str):
        match = _LAPS_BEHIND.match(raw_gap.strip())
        if match is None:
            raise InvalidRecordError(f"gap_to_leader inesperado: {raw_gap!r}")
        laps_behind = int(match[1])
        gap_to_leader = None
    else:
        gap_to_leader = _opt_float(raw, "gap_to_leader")

    return SessionResult(
        session_key=_int(raw, "session_key"),
        driver_number=_int(raw, "driver_number"),
        meeting_key=_opt_int(raw, "meeting_key"),
        position=_opt_int(raw, "position"),
        number_of_laps=_opt_int(raw, "number_of_laps"),
        points=_opt_float(raw, "points"),
        dnf=_bool(raw, "dnf"),
        dns=_bool(raw, "dns"),
        dsq=_bool(raw, "dsq"),
        duration=duration,
        gap_to_leader=gap_to_leader,
        laps_behind=laps_behind,
        q1=q1,
        q2=q2,
        q3=q3,
    )


def parse_lap(raw: RawRecord) -> Lap:
    """Converte um registro de `laps` (ignora os minissetores `segments_sector_*`)."""
    return Lap(
        session_key=_int(raw, "session_key"),
        driver_number=_int(raw, "driver_number"),
        lap_number=_int(raw, "lap_number"),
        meeting_key=_opt_int(raw, "meeting_key"),
        date_start=_opt_datetime(raw, "date_start"),
        lap_duration=_opt_float(raw, "lap_duration"),
        duration_sector_1=_opt_float(raw, "duration_sector_1"),
        duration_sector_2=_opt_float(raw, "duration_sector_2"),
        duration_sector_3=_opt_float(raw, "duration_sector_3"),
        i1_speed=_opt_int(raw, "i1_speed"),
        i2_speed=_opt_int(raw, "i2_speed"),
        st_speed=_opt_int(raw, "st_speed"),
        is_pit_out_lap=_bool(raw, "is_pit_out_lap"),
    )


def parse_stint(raw: RawRecord) -> Stint:
    """Converte um registro de `stints`."""
    return Stint(
        session_key=_int(raw, "session_key"),
        driver_number=_int(raw, "driver_number"),
        stint_number=_int(raw, "stint_number"),
        meeting_key=_opt_int(raw, "meeting_key"),
        compound=_opt_str(raw, "compound"),
        lap_start=_opt_int(raw, "lap_start"),
        lap_end=_opt_int(raw, "lap_end"),
        tyre_age_at_start=_opt_int(raw, "tyre_age_at_start"),
    )


def parse_pit_stop(raw: RawRecord) -> PitStop:
    """Converte um registro de `pit` (ignora `pit_duration`, deprecated)."""
    return PitStop(
        session_key=_int(raw, "session_key"),
        driver_number=_int(raw, "driver_number"),
        lap_number=_int(raw, "lap_number"),
        meeting_key=_opt_int(raw, "meeting_key"),
        date=_opt_datetime(raw, "date"),
        lane_duration=_opt_float(raw, "lane_duration"),
        stop_duration=_opt_float(raw, "stop_duration"),
    )


def _qualifying_phases(
    values: list[Any], key: str
) -> tuple[float | None, float | None, float | None]:
    if len(values) > 3:
        raise InvalidRecordError(f"{key!r} com mais de 3 fases: {values!r}")
    phases = [_as_float(value, key) for value in values]
    phases += [None] * (3 - len(phases))
    return phases[0], phases[1], phases[2]


def _int(raw: RawRecord, key: str) -> int:
    value = _opt_int(raw, key)
    if value is None:
        raise InvalidRecordError(f"campo obrigatório ausente: {key!r}")
    return value


def _opt_int(raw: RawRecord, key: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidRecordError(f"{key!r} precisa ser inteiro, veio {value!r}")
    return value


def _opt_float(raw: RawRecord, key: str) -> float | None:
    return _as_float(raw.get(key), key)


def _as_float(value: Any, key: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidRecordError(f"{key!r} precisa ser numérico, veio {value!r}")
    return float(value)


def _str(raw: RawRecord, key: str) -> str:
    value = _opt_str(raw, key)
    if not value:
        raise InvalidRecordError(f"campo obrigatório ausente: {key!r}")
    return value


def _opt_str(raw: RawRecord, key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidRecordError(f"{key!r} precisa ser texto, veio {value!r}")
    return value


def _bool(raw: RawRecord, key: str) -> bool:
    value = raw.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise InvalidRecordError(f"{key!r} precisa ser booleano, veio {value!r}")
    return value


def _opt_datetime(raw: RawRecord, key: str) -> datetime | None:
    value = _opt_str(raw, key)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRecordError(f"{key!r} não é uma data ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
