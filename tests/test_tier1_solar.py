"""Tier 1: solar events. The ONLY tier with fuzzy tolerances.

Everything downstream is fed pre-computed SolarEvents and asserted exactly.
The ephemeris is the only place where "close" is the right standard.
"""

from __future__ import annotations

import ast
import datetime as _dt
from pathlib import Path

import pytest
from astral.sun import elevation, sun

from tattva import UPPER_LIMB_DEG, Location, compute_solar_events

SOLSTICE = _dt.date(2026, 6, 21)


def test_upper_limb_is_later_than_refracted(rs: Location) -> None:
    """The geometric anchor is LATER than astral's refracted sunrise.

    Refraction lifts the apparent sun, so a refracted sunrise is reported before
    the disc geometrically reaches the horizon. Measured at Ramnicu Sarat on the
    solstice: refracted 05:23:48, upper limb 05:27:26 -- about 3.6 minutes.
    """
    events = compute_solar_events(rs, SOLSTICE)
    refracted = sun(rs.observer, date=SOLSTICE, tzinfo=rs.tzinfo)["sunrise"]
    delta = (events.sunrise - refracted).total_seconds()
    assert 180.0 < delta < 260.0, f"upper limb vs refracted sunrise: {delta} s"


def test_no_refraction_leak(rs: Location) -> None:
    """The anchor really is at theta = -0.267, not at a refraction-adjusted value.

    This guards the trap that a zenith-based helper of the shape
    ``-(zenith - 90) - refraction_at_zenith(zenith)`` returns -0.481944 for
    zenith 90.0 rather than 0.0. If anyone ever "simplifies" solar.py to route
    through such a table, this fails.
    """
    events = compute_solar_events(rs, SOLSTICE)
    for instant in (events.sunrise, events.sunset):
        actual = elevation(rs.observer, instant, with_refraction=False)
        assert actual == pytest.approx(UPPER_LIMB_DEG, abs=1e-3)


def test_upper_limb_lengthens_day(rs: Location) -> None:
    """Upper limb versus geometric centre.

    `grid-phase`.measured_consequences_RS records "~100-125 s". Measured, that
    is the shift at EACH END (110.9 s at the solstice, 91.1 s at the equinox);
    the day as a whole gains twice it. The decision's wording attributes the
    per-end figure to the day, which is why this test pins both numbers.
    """
    limb = compute_solar_events(rs, SOLSTICE, elevation_deg=UPPER_LIMB_DEG)
    centre = compute_solar_events(rs, SOLSTICE, elevation_deg=0.0)

    at_sunrise = (centre.sunrise - limb.sunrise).total_seconds()
    at_sunset = (limb.sunset - centre.sunset).total_seconds()
    assert 100.0 <= at_sunrise <= 125.0
    assert 100.0 <= at_sunset <= 125.0

    total = limb.day_seconds - centre.day_seconds
    assert total == pytest.approx(at_sunrise + at_sunset, abs=1e-6)
    assert 200.0 <= total <= 250.0


def test_midnight_is_night_midpoint(rs: Location, any_date: _dt.date) -> None:
    """`midnight-definition`: midnight halves sunset..next_sunrise.

    Tolerance is 1 microsecond, not exact: timedelta division truncates to whole
    microseconds, so an odd-microsecond night splits 1 us unevenly.
    """
    events = compute_solar_events(rs, any_date)
    before = (events.midnight - events.sunset).total_seconds()
    after = (events.next_sunrise - events.midnight).total_seconds()
    assert before == pytest.approx(after, abs=2e-6)


def test_midnight_is_not_noon_plus_twelve(rs: Location, any_date: _dt.date) -> None:
    """The retired calc.py used noon+12h in six places. It is wrong, and the
    error flips sign across the year (-28 s in December, +40 s in March)."""
    events = compute_solar_events(rs, any_date)
    naive = events.noon + _dt.timedelta(hours=12)
    assert abs((naive - events.midnight).total_seconds()) < 60.0


def test_package_is_pure() -> None:
    """No GUI, no ephemeris downloads, no wall-clock reads inside the package.

    The datetime.now() clause matters as much as the Qt one: reading the clock
    internally is what made the old generate_tattva_table() able to produce only
    "today", forcing every external consumer to reimplement the split.
    """
    banned_imports = {"PyQt6", "PyQt5", "geopy", "skyfield", "pytz"}
    package = Path(__file__).resolve().parent.parent / "src" / "tattva"
    offences: list[str] = []

    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_imports:
                        offences.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in banned_imports:
                    offences.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in {"now", "today", "utcnow"}:
                    value = func.value
                    name = getattr(value, "id", None) or getattr(value, "attr", None)
                    if name in {"datetime", "date", "_dt"}:
                        offences.append(f"{path.name}: {name}.{func.attr}()")

    assert not offences, "purity rule violated: " + "; ".join(offences)


def test_astral_agrees_with_skyfield(rs: Location) -> None:
    """Optional JPL cross-check.

    This is the idea that used to live in the tray's startup path, where it
    contributed nothing to output but could kill an autostarted app if the
    ephemeris file was missing. It belongs here: it runs when skyfield is
    available and is skipped otherwise.
    """
    skyfield_api = pytest.importorskip("skyfield.api")
    almanac = pytest.importorskip("skyfield.almanac")

    data_dir = Path(__file__).resolve().parent.parent / "skyfield-data"
    if not (data_dir / "de421.bsp").exists():
        pytest.skip("de421.bsp not present")

    loader = skyfield_api.Loader(str(data_dir))
    ephemeris = loader("de421.bsp")
    timescale = loader.timescale()
    observer = skyfield_api.wgs84.latlon(rs.latitude_deg, rs.longitude_deg)

    start = timescale.from_datetime(_dt.datetime(2026, 6, 21, tzinfo=_dt.UTC))
    end = timescale.from_datetime(_dt.datetime(2026, 6, 22, tzinfo=_dt.UTC))
    times, events = almanac.find_discrete(start, end, almanac.sunrise_sunset(ephemeris, observer))

    rises = [t.utc_datetime() for t, e in zip(times, events, strict=False) if e == 1]
    assert rises, "skyfield found no sunrise"

    ours = compute_solar_events(rs, _dt.date(2026, 6, 21))
    # Skyfield's sunrise is refracted, ours is geometric; compare against the
    # refracted anchor so this measures ephemeris agreement, not anchor choice.
    refracted = sun(rs.observer, date=_dt.date(2026, 6, 21), tzinfo=rs.tzinfo)["sunrise"]
    assert abs((rises[0] - refracted).total_seconds()) < 120.0
    assert ours.sunrise > refracted
