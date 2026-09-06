"""Tier 6: the content clocks -- doshas and organs.

Both divide the DISC-UP day rather than the collared tattva arcs (see
`organ-clock-anchor`), and both carry per-entry prose. Exact tolerances: like
tiers 2-5 these are fed pre-computed solar events, so nothing here is fuzzy.

The organ half of this file closes a real gap: tattva.organs shipped in the
tray for months with ZERO test coverage.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from tattva import Location, compute_solar_events
from tattva.doshas import (
    DOSHAS_PER_HALF,
    PHASES_PER_DOSHA,
    generate_dosha_table_from_solar,
    load_dosha_content,
    locate_dosha_from_solar,
)
from tattva.organs import (
    ORGANS_PER_HALF,
    PHASES_PER_ORGAN,
    generate_organ_table_from_solar,
    load_organ_content,
    locate_organ_from_solar,
)

SOLSTICE = _dt.date(2026, 6, 21)

# Words that would be true during ANY dosha. If one appears in `signs`, the
# instrument is broken before it is used -- see `cycle-apps-are-instruments`.
VAGUE = ("balanced", "centred", "centered", "harmonious", "in tune", "energised", "energized")


# ---------------------------------------------------------------- doshas

def test_dosha_table_has_18_periods(rs: Location, any_date: _dt.date) -> None:
    table = generate_dosha_table_from_solar(compute_solar_events(rs, any_date))
    assert len(table) == 2 * DOSHAS_PER_HALF * PHASES_PER_DOSHA == 18


def test_dosha_phases_partition_each_arc(rs: Location, any_date: _dt.date) -> None:
    """The 9 phases of a half sum exactly to that half -- no gap, no overlap."""
    solar = compute_solar_events(rs, any_date)
    table = generate_dosha_table_from_solar(solar)
    for half, expected in (("day", solar.day_seconds), ("night", solar.night_seconds)):
        rows = [p for p in table if p.half == half]
        assert sum(p.phase_seconds for p in rows) == pytest.approx(expected, abs=1e-9)
        assert rows[0].start == (solar.sunrise if half == "day" else solar.sunset)
        for earlier, later in zip(rows, rows[1:], strict=False):
            # 1 us tolerance: timedelta truncates to whole microseconds, so
            # consecutive spans can differ by that much at the seam.
            assert abs((later.start - earlier.end).total_seconds()) <= 2e-6


def test_dosha_order_continues_across_sunset(rs: Location, any_date: _dt.date) -> None:
    """Kapha -> Pitta -> Vata, wrapping exactly at sunset."""
    table = generate_dosha_table_from_solar(compute_solar_events(rs, any_date))
    assert [p.dosha for p in table[::PHASES_PER_DOSHA]] == [
        "Kapha", "Pitta", "Vata", "Kapha", "Pitta", "Vata",
    ]


def test_pitta_spans_solar_midnight(in_domain_location: Location, any_date: _dt.date) -> None:
    """DERIVED, not imposed -- and it matches the classical night pattern.

    The middle of three equal blocks contains the arc's midpoint, and by
    `midnight-definition` the night arc's midpoint IS solar midnight.
    """
    solar = compute_solar_events(in_domain_location, any_date)
    at_midnight = locate_dosha_from_solar(solar.midnight, solar)
    assert at_midnight.dosha == "Pitta"
    assert at_midnight.half == "night"


def test_vata_runs_pre_dawn(rs: Location, any_date: _dt.date) -> None:
    solar = compute_solar_events(rs, any_date)
    just_before = solar.next_sunrise - _dt.timedelta(minutes=5)
    assert locate_dosha_from_solar(just_before, solar).dosha == "Vata"


def test_dosha_locate_matches_table(rs: Location, any_date: _dt.date) -> None:
    solar = compute_solar_events(rs, any_date)
    for row in generate_dosha_table_from_solar(solar):
        midpoint = row.start + _dt.timedelta(seconds=row.phase_seconds / 2)
        found = locate_dosha_from_solar(midpoint, solar)
        assert (found.dosha, found.phase, found.half) == (row.dosha, row.phase, row.half)


def test_dosha_locate_boundary_semantics(rs: Location) -> None:
    """Half-open [start, end): an instant at a phase's own start is in it."""
    solar = compute_solar_events(rs, SOLSTICE)
    row = generate_dosha_table_from_solar(solar)[4]
    # A phase start locates to its OWN phase -- the bug this pins: before the
    # _index_for fix, 5 of 18 dosha and 30 of 60 organ starts flipped to the
    # previous phase through timedelta microsecond truncation.
    assert locate_dosha_from_solar(row.start, solar).phase_index == row.phase_index

    # Safely inside, and safely into the next one. NOT row.end - 1us: a
    # microsecond is exactly the snap tolerance, so that instant legitimately
    # rounds up to the next boundary.
    inside = row.start + _dt.timedelta(seconds=row.phase_seconds / 2)
    assert locate_dosha_from_solar(inside, solar).phase_index == row.phase_index
    assert locate_dosha_from_solar(row.end, solar).phase_index != row.phase_index


def test_dosha_day_and_night_lengths_differ(rs: Location) -> None:
    """The seasonal swing: ~311 min per dosha in June daylight, ~169 that night."""
    table = generate_dosha_table_from_solar(compute_solar_events(rs, SOLSTICE))
    day = next(p for p in table if p.half == "day")
    night = next(p for p in table if p.half == "night")
    assert day.dosha_seconds / 60 == pytest.approx(310.8, abs=0.2)
    assert night.dosha_seconds / 60 == pytest.approx(169.3, abs=0.2)


def test_dosha_measured_consequences_ramnicu_sarat(rs: Location) -> None:
    """Pins the figures recorded in DECISIONS `dosha-clock`."""
    for day, expected in (
        (_dt.date(2026, 9, 6), 258.2),
        (_dt.date(2026, 6, 21), 310.8),
        (_dt.date(2026, 12, 21), 171.8),
    ):
        table = generate_dosha_table_from_solar(compute_solar_events(rs, day))
        first = next(p for p in table if p.half == "day")
        assert first.dosha_seconds / 60 == pytest.approx(expected, abs=0.2)
        assert first.phase_seconds == pytest.approx(first.dosha_seconds / 3, abs=1e-9)


def test_dosha_pre_sunrise_belongs_to_previous_night(rs: Location) -> None:
    solar = compute_solar_events(rs, SOLSTICE)
    before_dawn = solar.sunrise - _dt.timedelta(minutes=30)
    assert locate_dosha_from_solar(before_dawn, solar).half == "night"


def test_dosha_content_has_all_four_sections() -> None:
    content = load_dosha_content()
    assert content.doshas == ("Kapha", "Pitta", "Vata")
    assert content.phases == ("Rising", "Peak", "Declining")
    for dosha in content.doshas:
        for key in ("qualities", "signs", "favourable", "avoid"):
            assert content.entries[dosha][key].strip()


def test_signs_are_substantive() -> None:
    """`signs` must be concrete enough to be WRONG.

    Crude on purpose -- it catches exactly the failure mode the decision warns
    about: agreeable prose that would confirm every system equally.
    """
    content = load_dosha_content()
    for dosha in content.doshas:
        signs = content.entries[dosha]["signs"]
        words = len(signs.split())
        assert 15 <= words <= 50, f"{dosha}: {words} words"
        lowered = signs.lower()
        for vague in VAGUE:
            assert vague not in lowered, f"{dosha} signs contain vague term {vague!r}"


# ---------------------------------------------------------------- organs

def test_organ_table_has_60_periods(rs: Location, any_date: _dt.date) -> None:
    table = generate_organ_table_from_solar(compute_solar_events(rs, any_date))
    assert len(table) == 2 * ORGANS_PER_HALF * PHASES_PER_ORGAN == 60


def test_organ_phases_partition_each_arc(rs: Location, any_date: _dt.date) -> None:
    solar = compute_solar_events(rs, any_date)
    table = generate_organ_table_from_solar(solar)
    for half, expected in (("day", solar.day_seconds), ("night", solar.night_seconds)):
        rows = [p for p in table if p.half == half]
        assert sum(p.phase_seconds for p in rows) == pytest.approx(expected, abs=1e-9)


def test_organ_night_uses_next_sunrise_not_86400(rs: Location) -> None:
    """Pins the fixed bug: the live path once used 86400 - daylight while the
    table used next_sunrise - sunset, so tray and table disagreed by minutes."""
    solar = compute_solar_events(rs, _dt.date(2026, 3, 20))
    night = [p for p in generate_organ_table_from_solar(solar) if p.half == "night"]
    assert sum(p.phase_seconds for p in night) == pytest.approx(solar.night_seconds, abs=1e-9)
    assert sum(p.phase_seconds for p in night) != pytest.approx(
        86400 - solar.day_seconds, abs=1.0
    )


def test_organ_locate_matches_table(rs: Location, any_date: _dt.date) -> None:
    solar = compute_solar_events(rs, any_date)
    for row in generate_organ_table_from_solar(solar):
        midpoint = row.start + _dt.timedelta(seconds=row.phase_seconds / 2)
        found = locate_organ_from_solar(midpoint, solar)
        assert (found.organ, found.phase, found.half) == (row.organ, row.phase, row.half)


def test_organ_content_validates() -> None:
    content = load_organ_content()
    assert len(content.organs_day) == len(content.organs_night) == ORGANS_PER_HALF
    assert len(content.qi_phases) == PHASES_PER_ORGAN
    for organ in content.organs_day + content.organs_night:
        assert len(content.phases[organ]) == PHASES_PER_ORGAN
