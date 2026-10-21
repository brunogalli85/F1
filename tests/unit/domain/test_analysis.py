import pytest

from f1.domain.analysis import (
    StintSummary,
    classification,
    driver_labels,
    fastest_laps,
    pit_summary,
    result_status,
    tyre_strategy,
)
from f1.domain.models import Driver, Lap, PitStop, SessionResult, Stint
from f1.domain.parsing import (
    parse_driver,
    parse_lap,
    parse_pit_stop,
    parse_session_result,
    parse_stint,
)


def make_result(driver_number, position=None, laps=57, **flags) -> SessionResult:
    return SessionResult(
        session_key=1,
        driver_number=driver_number,
        meeting_key=1,
        position=position,
        number_of_laps=laps,
        points=None,
        dnf=flags.get("dnf", False),
        dns=flags.get("dns", False),
        dsq=flags.get("dsq", False),
        duration=None,
        gap_to_leader=None,
        laps_behind=flags.get("laps_behind"),
        q1=None,
        q2=None,
        q3=None,
    )


def make_lap(driver_number, lap_number, duration, pit_out=False) -> Lap:
    return Lap(
        session_key=1,
        driver_number=driver_number,
        lap_number=lap_number,
        meeting_key=1,
        date_start=None,
        lap_duration=duration,
        duration_sector_1=None,
        duration_sector_2=None,
        duration_sector_3=None,
        i1_speed=None,
        i2_speed=None,
        st_speed=None,
        is_pit_out_lap=pit_out,
    )


def make_pit(driver_number, lap_number, stop=None, lane=20.0) -> PitStop:
    return PitStop(1, driver_number, lap_number, 1, None, lane, stop)


def make_stint(driver_number, stint_number, compound, lap_start, lap_end) -> Stint:
    return Stint(1, driver_number, stint_number, 1, compound, lap_start, lap_end, 0)


# ── classificação ─────────────────────────────────────────────────────────


def test_classification_from_real_race_puts_dnf_last(load_fixture):
    results = [parse_session_result(r) for r in reversed(load_fixture("session_result_race"))]

    ordered = classification(results)

    assert [r.driver_number for r in ordered] == [1, 16, 81, 23, 18]
    assert result_status(ordered[3]) == "+1 volta"
    assert result_status(ordered[-1]) == "DNF"


def test_classification_orders_unclassified_by_laps_completed():
    results = [
        make_result(31, laps=0, dnf=True),
        make_result(18, laps=8, dnf=True),
        make_result(1, position=1),
        make_result(27, laps=39, dnf=True),
    ]

    assert [r.driver_number for r in classification(results)] == [1, 27, 18, 31]


def test_classification_of_empty_session():
    assert classification([]) == []


@pytest.mark.parametrize(
    ("flags", "status"),
    [
        ({}, "Classificado"),
        ({"laps_behind": 2}, "+2 voltas"),
        ({"dnf": True}, "DNF"),
        ({"dns": True}, "DNS"),
        ({"dsq": True, "dnf": True}, "DSQ"),
    ],
)
def test_result_status(flags, status):
    assert result_status(make_result(1, **flags)) == status


def test_driver_labels_falls_back_to_number(load_fixture):
    drivers = [parse_driver(r) for r in load_fixture("drivers")]
    drivers.append(Driver(1, 99, None, None, None, None, None, None, None, None, None))

    labels = driver_labels(drivers)

    assert labels[1] == "VER"
    assert labels[99] == "#99"


# ── voltas mais rápidas ───────────────────────────────────────────────────


def test_fastest_laps_from_real_laps(load_fixture):
    laps = [parse_lap(r) for r in load_fixture("laps")]

    ranking = fastest_laps(laps)

    assert [(f.driver_number, f.lap_number) for f in ranking] == [(1, 1), (16, 1)]
    assert ranking[0].gap_to_fastest == 0.0
    assert ranking[1].gap_to_fastest == pytest.approx(117.799 - 111.736)


def test_fastest_laps_ignores_pit_out_laps_and_missing_times():
    laps = [
        make_lap(1, 1, None),
        make_lap(1, 2, 80.0, pit_out=True),
        make_lap(1, 3, 90.0),
        make_lap(44, 1, 89.5),
    ]

    ranking = fastest_laps(laps)

    assert [(f.driver_number, f.lap_number, f.lap_duration) for f in ranking] == [
        (44, 1, 89.5),
        (1, 3, 90.0),
    ]
    assert ranking[1].gap_to_fastest == 0.5


def test_fastest_laps_respects_top():
    laps = [make_lap(n, 1, 90.0 + n) for n in range(1, 6)]

    assert [f.driver_number for f in fastest_laps(laps, top=2)] == [1, 2]
    assert len(fastest_laps(laps, top=10)) == 5


def test_fastest_laps_without_valid_laps():
    assert fastest_laps([]) == []
    assert fastest_laps([make_lap(1, 1, None), make_lap(1, 2, 80.0, pit_out=True)]) == []


@pytest.mark.parametrize("top", [0, -1])
def test_fastest_laps_rejects_invalid_top(top):
    with pytest.raises(ValueError, match="top precisa ser >= 1"):
        fastest_laps([make_lap(1, 1, 90.0)], top=top)


# ── estratégia de pneus ───────────────────────────────────────────────────


def test_tyre_strategy_from_real_stints(load_fixture):
    stints = [parse_stint(r) for r in load_fixture("stints")]

    strategies = tyre_strategy(stints)

    assert [s.driver_number for s in strategies] == [1, 16]
    assert strategies[0].stints[0] == StintSummary("MEDIUM", 1, 35, 35, 0)
    assert [s.laps for s in strategies[0].stints] == [35, 1, 1, 20]


def test_tyre_strategy_orders_stints_and_handles_open_stint():
    stints = [make_stint(4, 2, "HARD", 20, None), make_stint(4, 1, "SOFT", 1, 19)]

    (strategy,) = tyre_strategy(stints)

    assert [s.compound for s in strategy.stints] == ["SOFT", "HARD"]
    assert strategy.stints[1].laps is None


def test_tyre_strategy_of_empty_session():
    assert tyre_strategy([]) == []


# ── pit stops ─────────────────────────────────────────────────────────────


def test_pit_summary_from_real_pit_data(load_fixture):
    stops = [parse_pit_stop(r) for r in load_fixture("pit")]

    summaries = {s.driver_number: s for s in pit_summary(stops)}

    assert summaries[1].stops == 3
    assert summaries[1].laps == (35, 36, 37)
    assert summaries[1].fastest_stop == 2.5


def test_pit_summary_sorts_by_fastest_stop_and_puts_unknown_last():
    stops = [
        make_pit(1, 30, stop=None),
        make_pit(16, 20, stop=3.1),
        make_pit(16, 40, stop=2.4, lane=21.5),
        make_pit(81, 25, stop=2.9),
    ]

    summaries = pit_summary(stops)

    assert [s.driver_number for s in summaries] == [16, 81, 1]
    assert summaries[0].stops == 2
    assert summaries[0].fastest_stop == 2.4
    assert summaries[0].total_lane_time == 41.5
    assert summaries[-1].fastest_stop is None


def test_pit_summary_of_session_without_stops():
    assert pit_summary([]) == []
