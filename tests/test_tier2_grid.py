"""Tier 2: the collar grid. Exact -- fed pre-computed solar events.

These tests ARE the `grid-phase` decision. If one fails, either the code or the
decision changed; both cases need a human.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from tattva import (
    ARC_MINIS,
    COLLAR_MINIS,
    LIT_MINIS,
    Location,
    build_grid,
    compute_solar_events,
    generate_table_from_grid,
    locate_from_grid,
)
from tattva.grid import build_grid_from_solar, position_at_ordinal

SOLSTICE = _dt.date(2026, 6, 21)


def test_day_arc_is_exactly_125_minis(rs: Location, any_date: _dt.date) -> None:
    grid = build_grid(rs, any_date)
    assert grid.day.seconds == pytest.approx(ARC_MINIS * grid.day.mini_seconds, abs=1e-6)
    assert grid.night.seconds == pytest.approx(ARC_MINIS * grid.night.mini_seconds, abs=1e-6)


def test_mini_day_is_lit_span_over_121(rs: Location, any_date: _dt.date) -> None:
    grid = build_grid(rs, any_date)
    assert grid.day.mini_seconds == pytest.approx(grid.solar.day_seconds / LIT_MINIS, abs=1e-9)


def test_aa_tejas_starts_at_sunrise(in_domain_location: Location, any_date: _dt.date) -> None:
    """THE decision: Akasha.Akasha.Tejas STARTS at geometric sunrise."""
    grid = build_grid(in_domain_location, any_date)
    tejas = position_at_ordinal(COLLAR_MINIS, grid.day, grid.solar)
    assert (tejas.mega, tejas.tattva, tejas.mini) == ("Akasha", "Akasha", "Tejas")
    assert tejas.mini_start == grid.solar.sunrise


def test_pp_tejas_ends_at_sunset(in_domain_location: Location, any_date: _dt.date) -> None:
    """The dusk mirror: Prithivi.Prithivi.Tejas ENDS at geometric sunset.

    1 us tolerance: timedelta arithmetic truncates to whole microseconds.
    """
    grid = build_grid(in_domain_location, any_date)
    tejas = position_at_ordinal(ARC_MINIS - COLLAR_MINIS - 1, grid.day, grid.solar)
    assert (tejas.mega, tejas.tattva, tejas.mini) == ("Prithivi", "Prithivi", "Tejas")
    assert abs((tejas.mini_end - grid.solar.sunset).total_seconds()) <= 2e-6


def test_twilight_collar_minis_are_named(rs: Location) -> None:
    """The collar is the creation order unfolding: space, then breeze, then the
    disc. And its mirror at dusk: dew, then earth/dark."""
    grid = build_grid(rs, SOLSTICE)
    names = [
        (p.mega, p.tattva, p.mini)
        for p in (position_at_ordinal(k, grid.day, grid.solar) for k in range(ARC_MINIS))
    ]
    assert names[0] == ("Akasha", "Akasha", "Akasha")
    assert names[1] == ("Akasha", "Akasha", "Vayu")
    assert names[ARC_MINIS - 2] == ("Prithivi", "Prithivi", "Apas")
    assert names[ARC_MINIS - 1] == ("Prithivi", "Prithivi", "Prithivi")


def test_arcs_tile_without_gap(rs: Location, any_date: _dt.date) -> None:
    """The tiling decision (2026-09-04): the night's closing collar uses
    TOMORROW's mini_day, so tonight's night arc ends exactly where tomorrow's
    day arc begins. Using today's mini instead would leave a +/-3 s gap or
    overlap near the equinoxes.
    """
    today = build_grid(rs, any_date)
    tomorrow = build_grid(rs, any_date + _dt.timedelta(days=1))
    assert today.day.end == today.night.start
    assert abs((today.night.end - tomorrow.day.start).total_seconds()) <= 2e-6


def test_night_tejas_centres_near_midnight(rs: Location, any_date: _dt.date) -> None:
    """By odd-n meridian symmetry the night Tejas mega auto-centres on midnight
    -- no anchoring needed, which is why the old Tejas override was redundant.

    It centres to within ~1.6 s rather than exactly, because the night arc is
    trimmed by today's collar at the start and tomorrow's at the end (the tiling
    choice). The offset is exactly half that collar difference.
    """
    grid = build_grid(rs, any_date)
    tejas = position_at_ordinal(2 * 25, grid.night, grid.solar)
    centre = tejas.mega_start + (tejas.mega_end - tejas.mega_start) / 2

    collar_start = COLLAR_MINIS * grid.solar.day_seconds / LIT_MINIS
    collar_end = COLLAR_MINIS * grid.solar.next_day_seconds / LIT_MINIS
    predicted = -(collar_end - collar_start) / 2

    assert (centre - grid.solar.midnight).total_seconds() == pytest.approx(predicted, abs=1e-3)
    assert abs((centre - grid.solar.midnight).total_seconds()) < 2.0


def test_locate_matches_table(rs: Location, any_date: _dt.date) -> None:
    """The unification test: the live path and the table path cannot diverge.

    The Java engine derives indices twice -- once building the table, once for
    the live position -- and the two can disagree at boundaries. Here one
    ordinal feeds both, so this proves the property structurally.
    """
    grid = build_grid(rs, any_date)
    for row in generate_table_from_grid(grid):
        midpoint = row.mini_start + _dt.timedelta(seconds=row.mini_seconds / 2)
        found = locate_from_grid(midpoint, grid)
        assert (found.arc, found.ordinal) == (row.arc, row.ordinal)
        assert (found.mega, found.tattva, found.mini) == (row.mega, row.tattva, row.mini)


def test_locate_boundary_semantics(rs: Location) -> None:
    """Half-open [start, end): an instant exactly at a mini's start belongs to
    that mini; one microsecond before its end still does."""
    grid = build_grid(rs, SOLSTICE)
    row = position_at_ordinal(60, grid.day, grid.solar)

    assert locate_from_grid(row.mini_start, grid).ordinal == 60
    assert locate_from_grid(row.mini_end - _dt.timedelta(microseconds=1), grid).ordinal == 60
    assert locate_from_grid(row.mini_end, grid).ordinal == 61


def test_table_is_chronological_and_complete(rs: Location, any_date: _dt.date) -> None:
    rows = generate_table_from_grid(build_grid(rs, any_date))
    assert len(rows) == 2 * ARC_MINIS
    assert [r.mini_start for r in rows] == sorted(r.mini_start for r in rows)
    assert sum(1 for r in rows if r.arc == "day") == ARC_MINIS


def test_measured_consequences_ramnicu_sarat(rs: Location) -> None:
    """Pins `grid-phase`.measured_consequences_RS against the machine.

    The recorded day:night ratio was 2.06:1; it re-measures 2.019:1. Pinning it
    here is what stops it drifting a third time.
    """
    grid = build_grid(rs, SOLSTICE)
    assert grid.day.mini_seconds / 60 == pytest.approx(7.705, abs=0.001)
    assert 2 * grid.day.mini_seconds / 60 == pytest.approx(15.41, abs=0.01)
    assert grid.day.seconds / 3600 == pytest.approx(16.0518, abs=0.0001)
    assert grid.night.seconds / 3600 == pytest.approx(7.9520, abs=0.0001)
    assert grid.day.seconds / grid.night.seconds == pytest.approx(2.019, abs=0.001)


def test_day_and_night_minis_differ(rs: Location) -> None:
    """Day and night minis have DIFFERENT durations -- a consequence of collar
    borrowing, not a bug. Previously undocumented; measured here so nobody
    "fixes" it later. Even at the equinox they differ by ~8%.
    """
    equinox = build_grid(rs, _dt.date(2026, 3, 20))
    ratio = equinox.day.mini_seconds / equinox.night.mini_seconds
    assert ratio == pytest.approx(1.0785, abs=0.001)

    june = build_grid(rs, SOLSTICE)
    assert june.day.mini_seconds / june.night.mini_seconds == pytest.approx(2.019, abs=0.005)


def test_grid_from_solar_matches_convenience_wrapper(rs: Location) -> None:
    solar = compute_solar_events(rs, SOLSTICE)
    assert build_grid_from_solar(solar).day.start == build_grid(rs, SOLSTICE).day.start


def test_collar_minis_are_flagged(rs: Location, any_date: _dt.date) -> None:
    """The 2 minis at each end of an arc fall outside the disc-up day, and say so.

    Consumers need this to distinguish the twilight collar from the lit span
    without re-deriving the ordinal arithmetic themselves.
    """
    grid = build_grid(rs, any_date)
    rows = generate_table_from_grid(grid)

    assert sum(1 for row in rows if row.is_collar) == 4 * COLLAR_MINIS

    for arc_rows in (rows[:ARC_MINIS], rows[ARC_MINIS:]):
        flagged = [row.ordinal for row in arc_rows if row.is_collar]
        assert flagged == [0, 1, ARC_MINIS - 2, ARC_MINIS - 1]

    # The lit span is exactly the non-collar minis of the day arc, and it runs
    # from geometric sunrise to geometric sunset.
    lit = [row for row in rows[:ARC_MINIS] if not row.is_collar]
    assert len(lit) == LIT_MINIS
    assert lit[0].mini_start == grid.solar.sunrise
    assert abs((lit[-1].mini_end - grid.solar.sunset).total_seconds()) <= 2e-6
