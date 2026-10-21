from datetime import UTC, datetime

import pytest

from f1.domain.parsing import (
    InvalidRecordError,
    parse_driver,
    parse_lap,
    parse_many,
    parse_meeting,
    parse_pit_stop,
    parse_session,
    parse_session_result,
    parse_stint,
)


def test_parse_meeting_from_api_format(load_fixture):
    meeting = parse_meeting(load_fixture("meetings")[0])

    assert meeting.meeting_key == 1251
    assert meeting.year == 2024
    assert meeting.meeting_name == "Qatar Grand Prix"
    assert meeting.circuit_type == "Permanent"
    assert meeting.date_start == datetime(2024, 11, 29, 13, 30, tzinfo=UTC)
    assert meeting.is_cancelled is False


def test_parse_session_from_api_format(load_fixture):
    sessions = [parse_session(raw) for raw in load_fixture("sessions")]

    race = next(s for s in sessions if s.session_key == 9655)
    assert (race.session_type, race.session_name, race.country_name) == ("Race", "Race", "Qatar")
    assert race.date_end == datetime(2024, 12, 1, 18, 0, tzinfo=UTC)


def test_parse_session_requires_date_start(load_fixture):
    raw = {**load_fixture("sessions")[0], "date_start": None}

    with pytest.raises(InvalidRecordError, match="date_start"):
        parse_session(raw)


def test_parse_driver_ignores_deprecated_country_code(load_fixture):
    driver = parse_driver(load_fixture("drivers")[0])

    assert driver.name_acronym == "VER"
    assert driver.team_name == "Red Bull Racing"
    assert not hasattr(driver, "country_code")


def test_parse_race_result_for_winner(load_fixture):
    result = parse_session_result(load_fixture("session_result_race")[0])

    assert result.position == 1
    assert result.duration == 5465.323
    assert result.gap_to_leader == 0.0
    assert result.laps_behind is None
    assert (result.q1, result.q2, result.q3) == (None, None, None)


@pytest.mark.parametrize(("gap", "laps"), [("+1 LAP", 1), ("+2 LAPS", 2), (" +3 LAPS ", 3)])
def test_parse_race_result_with_lapped_driver(gap, laps):
    result = parse_session_result({"session_key": 1, "driver_number": 23, "gap_to_leader": gap})

    assert result.laps_behind == laps
    assert result.gap_to_leader is None


def test_parse_race_result_for_dnf_driver(load_fixture):
    dnf = next(r for r in load_fixture("session_result_race") if r["dnf"])

    result = parse_session_result(dnf)

    assert result.dnf is True
    assert result.position is None
    assert result.gap_to_leader is None


def test_parse_qualifying_result_splits_phases(load_fixture):
    pole, second, q1_only = (
        parse_session_result(r) for r in load_fixture("session_result_qualifying")
    )

    assert (pole.q1, pole.q2, pole.q3) == (81.579, 80.687, 80.52)
    assert pole.duration is None
    assert pole.gap_to_leader == 0.0
    assert second.gap_to_leader == 0.055
    assert (q1_only.q1, q1_only.q2, q1_only.q3) == (82.594, None, None)
    assert q1_only.gap_to_leader == 1.353


def test_parse_qualifying_result_with_all_null_gaps():
    result = parse_session_result(
        {
            "session_key": 1,
            "driver_number": 2,
            "duration": [None, None, None],
            "gap_to_leader": [None],
        }
    )

    assert result.gap_to_leader is None
    assert (result.q1, result.q2, result.q3) == (None, None, None)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("gap_to_leader", "DNF", "gap_to_leader inesperado"),
        ("duration", [1.0, 2.0, 3.0, 4.0], "mais de 3 fases"),
        ("duration", ["x"], "numérico"),
        ("points", True, "numérico"),
        ("dnf", "no", "booleano"),
        ("position", 1.5, "inteiro"),
        ("driver_number", None, "driver_number"),
    ],
)
def test_parse_session_result_rejects_invalid_fields(load_fixture, field, value, message):
    raw = {**load_fixture("session_result_race")[0], field: value}

    with pytest.raises(InvalidRecordError, match=message):
        parse_session_result(raw)


def test_parse_lap_keeps_pit_out_flag_and_null_durations(load_fixture):
    raw = {**load_fixture("laps")[0], "lap_duration": None, "is_pit_out_lap": True}

    lap = parse_lap(raw)

    assert lap.lap_duration is None
    assert lap.is_pit_out_lap is True
    assert lap.duration_sector_1 == 34.809
    assert lap.date_start == datetime(2024, 12, 1, 16, 3, 33, 83000, tzinfo=UTC)


def test_parse_stint(load_fixture):
    stint = parse_stint(load_fixture("stints")[0])

    assert (stint.stint_number, stint.compound, stint.lap_start, stint.lap_end) == (
        1,
        "MEDIUM",
        1,
        35,
    )


def test_parse_pit_stop_with_missing_stop_duration(load_fixture):
    raw = next(r for r in load_fixture("pit") if r["stop_duration"] is None)

    stop = parse_pit_stop(raw)

    assert stop.stop_duration is None
    assert stop.lane_duration == raw["lane_duration"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024-12-01T16:00:00+03:00", datetime(2024, 12, 1, 13, 0, tzinfo=UTC)),
        ("2024-12-01T16:00:00", datetime(2024, 12, 1, 16, 0, tzinfo=UTC)),
    ],
)
def test_dates_are_normalized_to_utc(value, expected):
    stop = parse_pit_stop({"session_key": 1, "driver_number": 1, "lap_number": 1, "date": value})

    assert stop.date == expected


def test_invalid_date_is_rejected():
    with pytest.raises(InvalidRecordError, match="ISO 8601"):
        parse_pit_stop({"session_key": 1, "driver_number": 1, "lap_number": 1, "date": "ontem"})


def test_parse_many_counts_rejected_records_without_failing_the_batch(load_fixture, caplog):
    raws = load_fixture("stints")
    raws[1] = {**raws[1], "stint_number": None}

    result = parse_many(raws, parse_stint)

    assert len(result.records) == len(raws) - 1
    assert result.rejected == 1
    assert "registro rejeitado por parse_stint" in caplog.text


def test_parse_many_with_empty_input():
    result = parse_many([], parse_meeting)

    assert result.records == []
    assert result.rejected == 0


@pytest.mark.parametrize(
    "raw",
    [
        {"year": 2024, "meeting_name": "X"},
        {"meeting_key": 1, "year": 2024, "meeting_name": ""},
        {"meeting_key": 1, "year": 2024, "meeting_name": 7},
    ],
)
def test_parse_meeting_rejects_missing_or_invalid_required_fields(raw):
    with pytest.raises(InvalidRecordError):
        parse_meeting(raw)
