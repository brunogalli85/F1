"""Interface de linha de comando: subcomandos e formatação da saída no terminal."""

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime

from f1.config import Settings
from f1.domain.analysis import (
    classification,
    driver_labels,
    fastest_laps,
    pit_summary,
    result_status,
    tyre_strategy,
)
from f1.domain.models import Session, SessionResult
from f1.infrastructure.duckdb_store import DuckDbStore
from f1.infrastructure.openf1_client import OpenF1Client
from f1.pipelines.sync import sync_session, sync_year

SESSION_TYPES = ("Practice", "Qualifying", "Race")


class CliError(Exception):
    """Erro de uso que deve ser mostrado ao usuário sem traceback."""


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser de argumentos da CLI."""
    parser = argparse.ArgumentParser(
        prog="f1", description="Análises de Fórmula 1 sobre a OpenF1 API (cache local em DuckDB)."
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMANDO")

    sync = commands.add_parser("sync", help="baixa dados da API para o DuckDB")
    target = sync.add_mutually_exclusive_group(required=True)
    target.add_argument("--year", type=int, help="temporada (2023 em diante)")
    target.add_argument("--session-key", type=int, help="uma única sessão")
    sync.add_argument("--session-type", choices=SESSION_TYPES, help="restringe a um tipo de sessão")

    sessions = commands.add_parser("sessions", help="lista as sessões sincronizadas")
    sessions.add_argument("--year", type=int)
    sessions.add_argument("--country", help="país, ex.: Belgium")

    for name, help_text in (
        ("results", "classificação final"),
        ("fastest-laps", "melhor volta de cada piloto"),
        ("strategy", "stints e compostos por piloto"),
        ("pits", "pit stops e tempos"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--session-key", type=int, required=True)
        if name == "fastest-laps":
            command.add_argument("--top", type=_positive_int, default=None)

    return parser


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Executa a CLI.

    Args:
        argv: Argumentos (sem o nome do programa); por padrão, `sys.argv[1:]`.
        settings: Configuração; por padrão, lida do ambiente.
        now: Instante de referência para o `sync`; por padrão, o relógio atual (UTC).

    Returns:
        Código de saída (0 em caso de sucesso).

    Raises:
        CliError: Para erros de uso, como sessão não sincronizada.
    """
    args = build_parser().parse_args(argv)
    settings = settings or Settings.from_env()

    with DuckDbStore(settings.db_path) as store:
        if args.command == "sync":
            _run_sync(args, settings, store, now or datetime.now(UTC))
        elif args.command == "sessions":
            _print_sessions(store, args.year, args.country)
        else:
            session = store.session(args.session_key)
            if session is None:
                raise CliError(
                    f"sessão {args.session_key} não está no cache; "
                    f"rode `f1 sync --session-key {args.session_key}`"
                )
            print(_session_title(session))
            print()
            match args.command:
                case "results":
                    _print_results(store, session)
                case "fastest-laps":
                    _print_fastest_laps(store, session, args.top)
                case "strategy":
                    _print_strategy(store, session)
                case "pits":
                    _print_pits(store, session)
    return 0


def _run_sync(
    args: argparse.Namespace, settings: Settings, store: DuckDbStore, now: datetime
) -> None:
    with OpenF1Client(
        settings.openf1_base_url,
        timeout_s=settings.http_timeout_s,
        min_interval_s=settings.min_request_interval_s,
    ) as client:
        if args.session_key is not None:
            stats = sync_session(client, store, args.session_key, now)
        else:
            stats = sync_year(client, store, args.year, now, args.session_type)
    print(
        f"Sessões sincronizadas: {stats.sessions_synced} (puladas: {stats.sessions_skipped}) | "
        f"linhas lidas: {stats.rows_read}, gravadas: {stats.rows_written}, "
        f"rejeitadas: {stats.rows_rejected}"
    )
    print(format_table(["Tabela", "Linhas"], list(store.table_counts().items())))


def _print_sessions(store: DuckDbStore, year: int | None, country: str | None) -> None:
    sessions = store.sessions(year, country)
    if not sessions:
        print("Nenhuma sessão no cache. Rode `f1 sync --year <ano>` primeiro.")
        return
    rows = [
        [
            s.session_key,
            s.date_start.strftime("%Y-%m-%d %H:%M"),
            s.country_name or "-",
            s.circuit_short_name or "-",
            s.session_name,
            "cancelada" if s.is_cancelled else "",
        ]
        for s in sessions
    ]
    print(format_table(["Chave", "Início (UTC)", "País", "Circuito", "Sessão", ""], rows))


def _print_results(store: DuckDbStore, session: Session) -> None:
    results = classification(store.session_results(session.session_key))
    if not results:
        print("Sem resultado para esta sessão (a OpenF1 publica minutos após o resultado oficial).")
        return
    drivers = store.drivers(session.session_key)
    names = driver_labels(drivers)
    teams = {d.driver_number: d.team_name or "-" for d in drivers}

    if session.session_type == "Qualifying":
        headers = ["Pos", "Nº", "Piloto", "Equipe", "Q1", "Q2", "Q3", "Situação"]
        rows = [
            [
                _or_dash(r.position),
                r.driver_number,
                names.get(r.driver_number, f"#{r.driver_number}"),
                teams.get(r.driver_number, "-"),
                format_seconds(r.q1),
                format_seconds(r.q2),
                format_seconds(r.q3),
                result_status(r),
            ]
            for r in results
        ]
    else:
        headers = ["Pos", "Nº", "Piloto", "Equipe", "Voltas", "Tempo/Gap", "Pts"]
        rows = [
            [
                _or_dash(r.position),
                r.driver_number,
                names.get(r.driver_number, f"#{r.driver_number}"),
                teams.get(r.driver_number, "-"),
                _or_dash(r.number_of_laps),
                _time_or_gap(r, is_first=index == 0),
                "-" if r.points is None else f"{r.points:g}",
            ]
            for index, r in enumerate(results)
        ]
    print(format_table(headers, rows))


def _print_fastest_laps(store: DuckDbStore, session: Session, top: int | None) -> None:
    ranking = fastest_laps(store.laps(session.session_key), top)
    if not ranking:
        print("Sem voltas cronometradas para esta sessão.")
        return
    names = driver_labels(store.drivers(session.session_key))
    rows = [
        [
            position,
            names.get(lap.driver_number, f"#{lap.driver_number}"),
            lap.lap_number,
            format_seconds(lap.lap_duration),
            "-" if position == 1 else f"+{lap.gap_to_fastest:.3f}",
            _sector(lap.duration_sector_1),
            _sector(lap.duration_sector_2),
            _sector(lap.duration_sector_3),
        ]
        for position, lap in enumerate(ranking, start=1)
    ]
    print(format_table(["#", "Piloto", "Volta", "Tempo", "Gap", "S1", "S2", "S3"], rows))


def _print_strategy(store: DuckDbStore, session: Session) -> None:
    strategies = tyre_strategy(store.stints(session.session_key))
    if not strategies:
        print("Sem stints para esta sessão.")
        return
    names = driver_labels(store.drivers(session.session_key))
    order = _finishing_order(store.session_results(session.session_key))
    strategies.sort(key=lambda s: order.get(s.driver_number, len(order)))
    rows = [
        [
            names.get(s.driver_number, f"#{s.driver_number}"),
            len(s.stints),
            " > ".join(
                f"{stint.compound or '?'}({stint.laps if stint.laps is not None else '?'})"
                for stint in s.stints
            ),
        ]
        for s in strategies
    ]
    print(format_table(["Piloto", "Stints", "Compostos (voltas)"], rows))


def _print_pits(store: DuckDbStore, session: Session) -> None:
    summaries = pit_summary(store.pit_stops(session.session_key))
    if not summaries:
        print("Sem pit stops para esta sessão.")
        return
    names = driver_labels(store.drivers(session.session_key))
    rows = [
        [
            names.get(s.driver_number, f"#{s.driver_number}"),
            s.stops,
            ", ".join(str(lap) for lap in s.laps),
            "-" if s.fastest_stop is None else f"{s.fastest_stop:.1f}s",
            f"{s.total_lane_time:.1f}s",
        ]
        for s in summaries
    ]
    print(
        format_table(["Piloto", "Paradas", "Voltas", "Parada + rápida", "Tempo no pit lane"], rows)
    )


def format_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Formata uma tabela de texto alinhada por colunas."""
    cells = [[str(h) for h in headers], *[[str(v) for v in row] for row in rows]]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = [
        "  ".join(value.ljust(width) for value, width in zip(row, widths, strict=True))
        for row in cells
    ]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(line.rstrip() for line in lines)


def format_seconds(seconds: float | None) -> str:
    """Formata segundos como `M:SS.mmm` (ou `H:MM:SS.mmm` a partir de uma hora)."""
    if seconds is None:
        return "-"
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes}:{secs:02d}.{millis:03d}"


def _time_or_gap(result: SessionResult, *, is_first: bool) -> str:
    status = result_status(result)
    if status != "Classificado":
        return status
    if is_first or result.gap_to_leader is None:
        return format_seconds(result.duration)
    return f"+{result.gap_to_leader:.3f}s"


def _finishing_order(results: Sequence[SessionResult]) -> dict[int, int]:
    return {r.driver_number: index for index, r in enumerate(classification(results))}


def _session_title(session: Session) -> str:
    when = session.date_start.strftime("%Y-%m-%d")
    place = session.country_name or session.circuit_short_name or "?"
    return f"{place} {session.year} - {session.session_name} ({when}, sessão {session.session_key})"


def _sector(seconds: float | None) -> str:
    return "-" if seconds is None else f"{seconds:.3f}"


def _or_dash(value: object) -> str:
    return "-" if value is None else str(value)


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError(f"precisa ser >= 1, recebido {raw}")
    return value
