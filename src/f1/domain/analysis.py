"""Análises sobre os dados de uma sessão. Funções puras, sem I/O."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from f1.domain.models import Driver, Lap, PitStop, SessionResult, Stint


@dataclass(frozen=True, slots=True)
class FastestLap:
    """Melhor volta de um piloto na sessão."""

    driver_number: int
    lap_number: int
    lap_duration: float
    gap_to_fastest: float
    duration_sector_1: float | None
    duration_sector_2: float | None
    duration_sector_3: float | None


@dataclass(frozen=True, slots=True)
class StintSummary:
    """Um stint resumido para a estratégia de pneus."""

    compound: str | None
    lap_start: int | None
    lap_end: int | None
    laps: int | None
    tyre_age_at_start: int | None


@dataclass(frozen=True, slots=True)
class DriverStrategy:
    """Sequência de stints de um piloto."""

    driver_number: int
    stints: tuple[StintSummary, ...]


@dataclass(frozen=True, slots=True)
class DriverPitSummary:
    """Resumo das passagens pelo pit lane de um piloto."""

    driver_number: int
    stops: int
    laps: tuple[int, ...]
    fastest_stop: float | None
    total_lane_time: float


def driver_labels(drivers: Iterable[Driver]) -> dict[int, str]:
    """Mapeia número do carro para a sigla do piloto (ex.: `1 -> "VER"`)."""
    return {
        driver.driver_number: driver.name_acronym or f"#{driver.driver_number}"
        for driver in drivers
    }


def classification(results: Iterable[SessionResult]) -> list[SessionResult]:
    """Ordena os resultados na ordem da classificação final.

    Classificados vêm pela posição. Não classificados (DNF/DNS/DSQ sem posição) vêm depois,
    de quem completou mais voltas para quem completou menos.
    """
    return sorted(
        results,
        key=lambda r: (
            r.position is None,
            r.position if r.position is not None else 0,
            -(r.number_of_laps or 0),
            r.driver_number,
        ),
    )


def result_status(result: SessionResult) -> str:
    """Situação do piloto: `DSQ`, `DNS`, `DNF`, `+N volta(s)` ou `Classificado`."""
    if result.dsq:
        return "DSQ"
    if result.dns:
        return "DNS"
    if result.dnf:
        return "DNF"
    if result.laps_behind is not None:
        suffix = "volta" if result.laps_behind == 1 else "voltas"
        return f"+{result.laps_behind} {suffix}"
    return "Classificado"


def fastest_laps(laps: Iterable[Lap], top: int | None = None) -> list[FastestLap]:
    """Melhor volta de cada piloto, da mais rápida para a mais lenta.

    Voltas sem tempo e voltas de saída de box são descartadas.

    Args:
        laps: Voltas da sessão.
        top: Quantidade máxima de pilotos no resultado; `None` devolve todos.

    Raises:
        ValueError: Se `top` for menor que 1.
    """
    if top is not None and top < 1:
        raise ValueError(f"top precisa ser >= 1, recebido {top}")

    best: dict[int, Lap] = {}
    for lap in laps:
        if lap.lap_duration is None or lap.is_pit_out_lap:
            continue
        current = best.get(lap.driver_number)
        if current is None or lap.lap_duration < current.lap_duration:
            best[lap.driver_number] = lap

    ranked = sorted(best.values(), key=lambda lap: (lap.lap_duration, lap.driver_number))
    if not ranked:
        return []
    reference = ranked[0].lap_duration
    return [
        FastestLap(
            driver_number=lap.driver_number,
            lap_number=lap.lap_number,
            lap_duration=lap.lap_duration,
            gap_to_fastest=round(lap.lap_duration - reference, 3),
            duration_sector_1=lap.duration_sector_1,
            duration_sector_2=lap.duration_sector_2,
            duration_sector_3=lap.duration_sector_3,
        )
        for lap in ranked[:top]
    ]


def tyre_strategy(stints: Iterable[Stint]) -> list[DriverStrategy]:
    """Agrupa os stints por piloto, em ordem de stint, ordenando os pilotos pelo número."""
    by_driver: dict[int, list[Stint]] = defaultdict(list)
    for stint in stints:
        by_driver[stint.driver_number].append(stint)

    return [
        DriverStrategy(
            driver_number=driver_number,
            stints=tuple(
                _summarize_stint(stint)
                for stint in sorted(by_driver[driver_number], key=lambda s: s.stint_number)
            ),
        )
        for driver_number in sorted(by_driver)
    ]


def pit_summary(pit_stops: Iterable[PitStop]) -> list[DriverPitSummary]:
    """Resumo de pit stops por piloto, do pit stop mais rápido para o mais lento.

    Pilotos sem `stop_duration` registrado (dado disponível desde o GP dos EUA 2024)
    vão para o fim.
    """
    by_driver: dict[int, list[PitStop]] = defaultdict(list)
    for stop in pit_stops:
        by_driver[stop.driver_number].append(stop)

    summaries = []
    for driver_number, stops in by_driver.items():
        stop_times = [s.stop_duration for s in stops if s.stop_duration is not None]
        summaries.append(
            DriverPitSummary(
                driver_number=driver_number,
                stops=len(stops),
                laps=tuple(sorted(s.lap_number for s in stops)),
                fastest_stop=min(stop_times) if stop_times else None,
                total_lane_time=round(sum(s.lane_duration or 0.0 for s in stops), 3),
            )
        )
    return sorted(
        summaries,
        key=lambda s: (s.fastest_stop is None, s.fastest_stop or 0.0, s.driver_number),
    )


def _summarize_stint(stint: Stint) -> StintSummary:
    laps = None
    if stint.lap_start is not None and stint.lap_end is not None:
        laps = stint.lap_end - stint.lap_start + 1
    return StintSummary(
        compound=stint.compound,
        lap_start=stint.lap_start,
        lap_end=stint.lap_end,
        laps=laps,
        tyre_age_at_start=stint.tyre_age_at_start,
    )
