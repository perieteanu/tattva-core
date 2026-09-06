"""Shared fixtures.

Latitudes deliberately span the interesting cases, following astrolabe's
conftest: both hemispheres, the near-equatorial degenerate zone, the band where
astral returns DISORDERED events without raising (64..66), and beyond the
domain.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from tattva import Location

RAMNICU_SARAT = Location(
    name="Ramnicu Sarat",
    region="Romania",
    latitude_deg=45.37642,
    longitude_deg=27.04882,
    timezone="Europe/Bucharest",
)

BUENOS_AIRES = Location(
    name="Buenos Aires",
    region="Argentina",
    latitude_deg=-34.61315,
    longitude_deg=-58.37723,
    timezone="America/Argentina/Buenos_Aires",
)

QUITO = Location(
    name="Quito",
    region="Ecuador",
    latitude_deg=-0.18065,
    longitude_deg=-78.46784,
    timezone="America/Guayaquil",
)

TROMSO = Location(
    name="Tromso",
    region="Norway",
    latitude_deg=69.6492,
    longitude_deg=18.9553,
    timezone="Europe/Oslo",
)

# Equinoxes, solstices, and the date astrolabe uses as its worst-residual case.
DATES = (
    _dt.date(2026, 3, 20),
    _dt.date(2026, 6, 21),
    _dt.date(2026, 9, 22),
    _dt.date(2026, 12, 21),
    _dt.date(2026, 4, 16),
)


@pytest.fixture
def rs() -> Location:
    return RAMNICU_SARAT


@pytest.fixture(params=DATES, ids=lambda d: d.isoformat())
def any_date(request) -> _dt.date:
    return request.param


@pytest.fixture(params=[RAMNICU_SARAT, BUENOS_AIRES, QUITO], ids=lambda loc: loc.name)
def in_domain_location(request) -> Location:
    return request.param
