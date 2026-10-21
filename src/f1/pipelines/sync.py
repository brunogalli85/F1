"""Pipeline que sincroniza dados da OpenF1 para o cache DuckDB."""

import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from f1.domain.models import Session, SyncRun
from f1.domain.parsing import (
    ParseResult,
    RawRecord,
    parse_driver,
    parse_lap,
    parse_many,
    parse_meeting,
    parse_pit_stop,
    parse_session,
    parse_session_result,
    parse_stint,
)
from f1.infrastructure.duckdb_store import DuckDbStore
from f1.infrastructure.openf1_client import FilterValue, OpenF1Client

logger = logging.getLogger(__name__)

# Acima desta fração de registros rejeitados em um endpoint, o contrato da API mudou
# e é melhor falhar do que gravar dados incompletos.
MAX_REJECTED_RATIO = 0.1

_SESSION_ENDPOINTS: tuple[tuple[str, Callable[[RawRecord], Any]], ...] = (
    ("drivers", parse_driver),
    ("session_result", parse_session_result),
    ("laps", parse_lap),
    ("stints", parse_stint),
    ("pit", parse_pit_stop),
)


class SyncError(RuntimeError):
    """A sincronização não pôde ser concluída."""


@dataclass(slots=True)
class SyncStats:
    """Volumes de uma execução de sincronização."""

    sessions_synced: int = 0
    sessions_skipped: int = 0
    rows_read: int = 0
    rows_written: int = 0
    rows_rejected: int = 0


def sync_year(
    client: OpenF1Client,
    store: DuckDbStore,
    year: int,
    now: datetime,
    session_type: str | None = None,
) -> SyncStats:
    """Sincroniza meetings, sessões e dados das sessões encerradas de uma temporada.

    Args:
        client: Cliente da OpenF1.
        store: Cache DuckDB de destino.
        year: Temporada.
        now: Instante de referência (UTC); sessões que terminam depois dele são puladas.
        session_type: Restringe a um tipo de sessão (`Practice`, `Qualifying`, `Race`).

    Returns:
        Volumes da execução.

    Raises:
        SyncError: Se a taxa de registros rejeitados passar do limite.
        OpenF1Error: Se a API falhar.
    """
    scope = f"year={year}" + (f" session_type={session_type}" if session_type else "")
    started_at = datetime.now(UTC)
    stats = SyncStats()

    session_filters: dict[str, FilterValue] = {"year": year}
    if session_type:
        session_filters["session_type"] = session_type
    _load(client, store, stats, "meetings", {"year": year}, parse_meeting)
    sessions = _load(client, store, stats, "sessions", session_filters, parse_session)

    for session in sorted(sessions.records, key=lambda s: s.date_start):
        _sync_session_data(client, store, stats, session, now)

    _record_run(store, scope, started_at, stats)
    return stats


def sync_session(
    client: OpenF1Client, store: DuckDbStore, session_key: int, now: datetime
) -> SyncStats:
    """Sincroniza uma única sessão (e o meeting a que ela pertence).

    Args:
        client: Cliente da OpenF1.
        store: Cache DuckDB de destino.
        session_key: Chave da sessão.
        now: Instante de referência (UTC); a sessão é pulada se ainda não terminou.

    Returns:
        Volumes da execução.

    Raises:
        SyncError: Se a sessão não existir ou a taxa de rejeitados passar do limite.
        OpenF1Error: Se a API falhar.
    """
    started_at = datetime.now(UTC)
    stats = SyncStats()

    sessions = _load(client, store, stats, "sessions", {"session_key": session_key}, parse_session)
    if not sessions.records:
        raise SyncError(f"sessão {session_key} não encontrada na OpenF1")
    session = sessions.records[0]
    _load(client, store, stats, "meetings", {"meeting_key": session.meeting_key}, parse_meeting)
    _sync_session_data(client, store, stats, session, now)

    _record_run(store, f"session_key={session_key}", started_at, stats)
    return stats


def _sync_session_data(
    client: OpenF1Client, store: DuckDbStore, stats: SyncStats, session: Session, now: datetime
) -> None:
    label = f"{session.session_key} ({session.country_name} - {session.session_name})"
    if session.is_cancelled:
        logger.info("sessão %s cancelada; pulando", label)
        stats.sessions_skipped += 1
        return
    if session.date_end is None or session.date_end > now:
        logger.info("sessão %s ainda não terminou; pulando", label)
        stats.sessions_skipped += 1
        return

    # Busca tudo antes de gravar, para que a sessão entre no banco em uma única transação.
    batches = [
        _fetch(client, stats, endpoint, {"session_key": session.session_key}, parser)
        for endpoint, parser in _SESSION_ENDPOINTS
    ]
    with store.transaction():
        written = sum(store.upsert(batch.records) for batch in batches)
    stats.rows_written += written
    stats.sessions_synced += 1
    logger.info("sessão %s sincronizada: %d linhas", label, written)


def _load[T](
    client: OpenF1Client,
    store: DuckDbStore,
    stats: SyncStats,
    endpoint: str,
    filters: Mapping[str, FilterValue],
    parser: Callable[[RawRecord], T],
) -> ParseResult[T]:
    parsed = _fetch(client, stats, endpoint, filters, parser)
    with store.transaction():
        stats.rows_written += store.upsert(parsed.records)
    return parsed


def _fetch[T](
    client: OpenF1Client,
    stats: SyncStats,
    endpoint: str,
    filters: Mapping[str, FilterValue],
    parser: Callable[[RawRecord], T],
) -> ParseResult[T]:
    raws = client.get(endpoint, filters)
    parsed = parse_many(raws, parser)
    stats.rows_read += len(raws)
    stats.rows_rejected += parsed.rejected
    if raws and parsed.rejected / len(raws) > MAX_REJECTED_RATIO:
        raise SyncError(
            f"{endpoint} {dict(filters)}: {parsed.rejected} de {len(raws)} registros rejeitados "
            f"(limite {MAX_REJECTED_RATIO:.0%})"
        )
    return parsed


def _record_run(store: DuckDbStore, scope: str, started_at: datetime, stats: SyncStats) -> None:
    run = SyncRun(
        run_id=str(uuid.uuid4()),
        scope=scope,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        sessions_synced=stats.sessions_synced,
        sessions_skipped=stats.sessions_skipped,
        rows_read=stats.rows_read,
        rows_written=stats.rows_written,
        rows_rejected=stats.rows_rejected,
    )
    store.upsert([run])
    logger.info(
        "sync %s concluído (run_id=%s): %d sessões, %d puladas, %d lidas, %d gravadas, %d rejeitadas",
        scope,
        run.run_id,
        stats.sessions_synced,
        stats.sessions_skipped,
        stats.rows_read,
        stats.rows_written,
        stats.rows_rejected,
    )
