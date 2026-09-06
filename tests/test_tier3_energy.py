"""Tier 3: four-point cosine energy. Exact -- fed pre-computed solar events."""

from __future__ import annotations

import datetime as _dt

import pytest

from tattva import Location, compute_energy_from_solar, compute_solar_events

SOLSTICE = _dt.date(2026, 6, 21)


def test_anchor_values(rs: Location, any_date: _dt.date) -> None:
    """`energy-four-point`, exactly: yin 100% at midnight, 50/50 at sunrise and
    sunset, yang 100% at noon."""
    solar = compute_solar_events(rs, any_date)
    assert compute_energy_from_solar(solar.midnight, solar).yin == pytest.approx(1.0, abs=1e-12)
    assert compute_energy_from_solar(solar.sunrise, solar).yang == pytest.approx(0.5, abs=1e-12)
    assert compute_energy_from_solar(solar.noon, solar).yang == pytest.approx(1.0, abs=1e-12)
    assert compute_energy_from_solar(solar.sunset, solar).yang == pytest.approx(0.5, abs=1e-12)


def test_yin_yang_complement(rs: Location, any_date: _dt.date) -> None:
    """yang + yin == 1 everywhere.

    This is the regression test for the shipped bug: the retired model computed
    `yang = 1 - yin` BEFORE clamping each independently, so once progress went
    negative both saturated and the invariant broke.
    """
    solar = compute_solar_events(rs, any_date)
    span = (solar.next_sunrise - solar.sunrise).total_seconds()
    for step in range(1000):
        when = solar.sunrise + _dt.timedelta(seconds=span * step / 1000)
        energy = compute_energy_from_solar(when, solar)
        assert energy.yang + energy.yin == pytest.approx(1.0, abs=1e-12)
        assert 0.0 <= energy.yang <= 1.0


def test_no_inverted_polarity_after_midnight(rs: Location) -> None:
    """The shipped tray showed 100% yang / 0% yin from local midnight until
    sunrise -- peak yang at the deepest yin hours of the night.

    Named after the bug. At 02:00 the night is still strongly yin.
    """
    solar = compute_solar_events(rs, _dt.date(2026, 9, 4))
    when = _dt.datetime(2026, 9, 4, 2, 0, tzinfo=rs.tzinfo)
    energy = compute_energy_from_solar(when, solar)
    assert energy.yin > 0.8, f"02:00 should be deep yin, got yin={energy.yin}"
    assert energy.yang < 0.2


def test_yin_peaks_at_midnight_not_elsewhere(rs: Location) -> None:
    """Sample the whole night; the maximum yin is at midnight."""
    solar = compute_solar_events(rs, SOLSTICE)
    span = (solar.next_sunrise - solar.sunset).total_seconds()
    samples = [
        (compute_energy_from_solar(solar.sunset + _dt.timedelta(seconds=span * i / 400), solar).yin,
         solar.sunset + _dt.timedelta(seconds=span * i / 400))
        for i in range(401)
    ]
    peak_yin, peak_at = max(samples)
    assert peak_yin == pytest.approx(1.0, abs=1e-3)
    assert abs((peak_at - solar.midnight).total_seconds()) < span / 400


def test_cosine_easing_is_flat_at_anchors(rs: Location) -> None:
    """The (1 - cos(p*pi))/2 promise: zero derivative at every anchor, so the
    curve is smooth there rather than kinked as the retired linear model was."""
    solar = compute_solar_events(rs, SOLSTICE)
    delta = _dt.timedelta(seconds=1)
    for anchor in (solar.sunrise, solar.noon, solar.sunset, solar.midnight):
        before = compute_energy_from_solar(anchor - delta, solar).yang
        after = compute_energy_from_solar(anchor + delta, solar).yang
        derivative = (after - before) / 2.0
        assert abs(derivative) < 1e-4, f"kink at {anchor}: d={derivative}"


def test_monotone_between_anchors(rs: Location) -> None:
    """Yang rises sunrise->noon and falls noon->sunset, without wobble."""
    solar = compute_solar_events(rs, SOLSTICE)

    span = (solar.noon - solar.sunrise).total_seconds()
    rising = [
        compute_energy_from_solar(solar.sunrise + _dt.timedelta(seconds=span * i / 200), solar).yang
        for i in range(201)
    ]
    assert all(b >= a - 1e-12 for a, b in zip(rising, rising[1:], strict=False))

    span = (solar.sunset - solar.noon).total_seconds()
    falling = [
        compute_energy_from_solar(solar.noon + _dt.timedelta(seconds=span * i / 200), solar).yang
        for i in range(201)
    ]
    assert all(b <= a + 1e-12 for a, b in zip(falling, falling[1:], strict=False))


def test_segments_are_labelled(rs: Location) -> None:
    solar = compute_solar_events(rs, SOLSTICE)
    midday = solar.sunrise + (solar.noon - solar.sunrise) / 2
    afternoon = solar.noon + (solar.sunset - solar.noon) / 2
    evening = solar.sunset + (solar.midnight - solar.sunset) / 2
    assert compute_energy_from_solar(midday, solar).segment == "sunrise_to_noon"
    assert compute_energy_from_solar(afternoon, solar).segment == "noon_to_sunset"
    assert compute_energy_from_solar(evening, solar).segment == "sunset_to_midnight"


def test_no_civil_twilight_fields() -> None:
    """`division-anchor` rejected civil twilight as an anchor. SolarEvents must
    not carry dawn/dusk at all -- their absence is what makes regression to the
    retired six-point model structurally impossible."""
    from tattva import SolarEvents

    fields = SolarEvents.__dataclass_fields__
    for banned in ("dawn", "dusk", "next_dawn"):
        assert banned not in fields
