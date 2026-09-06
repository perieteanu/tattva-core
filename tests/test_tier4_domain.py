"""Tier 4: the solar domain. Where the model must refuse to answer.

No fixture in any of the four repos covered this before. It is where the
highest-severity finding in the astrolabe note lives -- silent fabrication --
and where astral itself is untrustworthy.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from tattva import Location, OutsideSolarDomainError, build_grid, compute_solar_events

from .conftest import TROMSO

SOLSTICE = _dt.date(2026, 6, 21)
MIDWINTER = _dt.date(2026, 12, 21)


def test_polar_day_raises() -> None:
    with pytest.raises(OutsideSolarDomainError) as excinfo:
        compute_solar_events(TROMSO, SOLSTICE)
    assert excinfo.value.reason in {"no_sunrise", "no_sunset"}


def test_polar_night_raises() -> None:
    with pytest.raises(OutsideSolarDomainError) as excinfo:
        compute_solar_events(TROMSO, MIDWINTER)
    assert excinfo.value.reason in {"no_sunrise", "no_sunset"}


def test_disordered_arc_raises() -> None:
    """THE test this whole tier exists for.

    At latitude 66.0 on the solstice -- INSIDE the nominal ~66.6 deg domain --
    astral returns a setting crossing BEFORE the rising one (set 21:35 before
    rise 22:51 UTC) and raises nothing at all. Both are genuine -0.267 deg
    crossings; astral simply searches within one calendar day and the sun barely
    dips. A naive (sunset - sunrise) is then NEGATIVE, mini_day is negative, and
    the collar arithmetic runs backwards to build a silently inverted grid.

    So the domain gate cannot be a try/except around astral. It must validate
    ordering explicitly, which is what SolarEvents.__post_init__ does.
    """
    location = Location("Edge", "Test", 66.0, 27.05, "Europe/Bucharest")
    with pytest.raises(OutsideSolarDomainError) as excinfo:
        compute_solar_events(location, SOLSTICE)
    assert excinfo.value.reason == "arc_disordered"


@pytest.mark.parametrize("latitude", [64.0, 65.0, 65.5, 66.0])
def test_disordered_band_all_raise(latitude: float) -> None:
    """The disordered band is wider than the one latitude that revealed it: it
    bites from about 64 deg up, well inside the nominal domain."""
    location = Location("Edge", "Test", latitude, 27.05, "Europe/Bucharest")
    with pytest.raises(OutsideSolarDomainError):
        compute_solar_events(location, SOLSTICE)


def test_error_carries_context() -> None:
    location = Location("Edge", "Test", 66.0, 27.05, "Europe/Bucharest")
    with pytest.raises(OutsideSolarDomainError) as excinfo:
        compute_solar_events(location, SOLSTICE)
    error = excinfo.value
    assert error.latitude_deg == 66.0
    assert error.longitude_deg == 27.05
    assert error.date == SOLSTICE
    assert error.elevation_deg == pytest.approx(-0.267)
    assert error.reason
    assert "66.0" in str(error)


def test_is_a_value_error() -> None:
    """Subclassing ValueError keeps existing bare `except ValueError` callers
    working while new code can catch the precise type."""
    assert issubclass(OutsideSolarDomainError, ValueError)


def test_never_fabricates() -> None:
    """The retired code returned hardcoded 05:25 / 21:03 / 13:15 on failure --
    well-formed, plausible, entirely wrong, and dated TODAY rather than the date
    requested. `division-anchor` requires raising instead. Nothing may come back
    from an undefined location.
    """
    for location, day in ((TROMSO, SOLSTICE), (TROMSO, MIDWINTER)):
        with pytest.raises(OutsideSolarDomainError):
            compute_solar_events(location, day)
        with pytest.raises(OutsideSolarDomainError):
            build_grid(location, day)


def test_domain_boundary_scan() -> None:
    """Sweep the edge. Every latitude either raises, or yields BOTH arcs
    positive -- there is no third outcome, and in particular no silent negative
    day length anywhere in the band.
    """
    defined: list[float] = []
    for tenth in range(600, 701):
        latitude = tenth / 10.0
        location = Location("Scan", "Test", latitude, 27.05, "Europe/Bucharest")
        try:
            events = compute_solar_events(location, SOLSTICE)
        except OutsideSolarDomainError:
            continue
        assert events.day_seconds > 0.0
        assert events.night_seconds > 0.0
        defined.append(latitude)

    assert defined, "nothing was defined in the 60-70 sweep"
    assert max(defined) < 66.6, f"defined above the polar circle: {max(defined)}"


def test_in_domain_locations_are_fine(in_domain_location: Location, any_date: _dt.date) -> None:
    """The gate must not be over-eager: ordinary latitudes keep working."""
    events = compute_solar_events(in_domain_location, any_date)
    assert events.day_seconds > 0.0
    assert events.night_seconds > 0.0
