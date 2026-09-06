"""Solar tattva model -- pure, GUI-free, location-parameterised.

Implements the canonical decisions in docs-yaml/DECISIONS.yaml:
`division-anchor`, `grid-phase`, `energy-four-point`, `midnight-definition`.

PURITY RULE. Nothing in this package may import PyQt6, geopy or skyfield, or
call datetime.now(). The now() clause matters as much as the Qt one: it is
exactly why astrolabe's make_fixtures.py had to reimplement the 5x5x5 split
locally, the old generate_tattva_table() being able to produce only "today".
Every function takes its instant from the caller. Enforced by
tests/test_tier1_solar.py::test_package_is_pure.
"""

from .energy import Energy, compute_energy_from_solar
from .errors import OutsideSolarDomainError
from .grid import (
    ARC_MINIS,
    COLLAR_MINIS,
    LIT_MINIS,
    TATTVAS,
    Arc,
    Grid,
    Position,
    build_grid,
    build_grid_from_solar,
    generate_table,
    generate_table_from_grid,
    locate,
    locate_from_grid,
)
from .location import Location
from .solar import (
    GEOMETRIC_CENTRE_DEG,
    UPPER_LIMB_DEG,
    SolarEvents,
    compute_solar_events,
)

__all__ = [
    "ARC_MINIS",
    "COLLAR_MINIS",
    "GEOMETRIC_CENTRE_DEG",
    "LIT_MINIS",
    "TATTVAS",
    "UPPER_LIMB_DEG",
    "Arc",
    "Energy",
    "Grid",
    "Location",
    "OutsideSolarDomainError",
    "Position",
    "SolarEvents",
    "build_grid",
    "build_grid_from_solar",
    "compute_energy_from_solar",
    "compute_solar_events",
    "generate_table",
    "generate_table_from_grid",
    "locate",
    "locate_from_grid",
]
