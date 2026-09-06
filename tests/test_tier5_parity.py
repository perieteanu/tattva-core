"""Tier 5: parity against the golden fixture.

Exact everywhere. The fixture is generated from this same model, so this tier
is a CHANGE DETECTOR, not an independent oracle: it fails when behaviour moves,
which is exactly what you want when four repos must agree on one model. The
independent checks live in tiers 1-4.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from tattva import (
    Location,
    OutsideSolarDomainError,
    build_grid,
    compute_energy_from_solar,
    compute_solar_events,
    generate_table_from_grid,
)

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden_model.json"


@pytest.fixture(scope="module")
def golden() -> dict:
    if not GOLDEN.exists():  # pragma: no cover
        pytest.skip("golden_model.json missing; run tests/make_golden.py")
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _location(golden: dict, name: str) -> Location:
    spec = golden["locations"][name]
    return Location(
        name=name,
        region="fixture",
        latitude_deg=spec["latitude_deg"],
        longitude_deg=spec["longitude_deg"],
        timezone=spec["timezone"],
    )


def test_solar_matches_golden(golden: dict) -> None:
    for row in golden["solar"]:
        location = _location(golden, row["location"])
        events = compute_solar_events(location, _dt.date.fromisoformat(row["date"]))
        for field in ("sunrise", "noon", "sunset", "next_sunrise", "next_sunset", "midnight"):
            assert getattr(events, field).isoformat() == row[field], f"{row['location']} {field}"


def test_energy_matches_golden(golden: dict) -> None:
    cache: dict[tuple[str, str], object] = {}
    for row in golden["energy"]:
        key = (row["location"], row["date"])
        if key not in cache:
            cache[key] = compute_solar_events(
                _location(golden, row["location"]), _dt.date.fromisoformat(row["date"])
            )
        energy = compute_energy_from_solar(_dt.datetime.fromisoformat(row["time"]), cache[key])
        assert energy.yang == pytest.approx(row["yang"], abs=1e-9)
        assert energy.yin == pytest.approx(row["yin"], abs=1e-9)
        assert energy.segment == row["segment"]
        assert energy.yang_dir == row["yang_dir"]


def test_tables_match_golden(golden: dict) -> None:
    for table in golden["tables"]:
        location = _location(golden, table["location"])
        grid = build_grid(location, _dt.date.fromisoformat(table["date"]))
        rows = generate_table_from_grid(grid)
        assert len(rows) == len(table["periods"])
        for row, expected in zip(rows, table["periods"], strict=True):
            assert row.arc == expected["arc"]
            assert row.ordinal == expected["ordinal"]
            assert row.mini_start.isoformat() == expected["time"]
            assert row.mega == expected["mega_tattva"]
            assert row.tattva == expected["tattva"]
            assert row.mini == expected["mini_tattva"]
            assert row.is_special == expected["is_special"]
            assert row.mini_seconds == pytest.approx(expected["mini_seconds"], abs=1e-9)


def test_undefined_cases_still_raise(golden: dict) -> None:
    """The polar and disordered cases must keep refusing, with the same reason."""
    assert golden["undefined"], "fixture records no undefined cases"
    for case in golden["undefined"]:
        name = case["location"]
        if name.startswith("Edge "):
            location = Location(
                "Edge", "Test", float(name.split()[1]), 27.05, "Europe/Bucharest"
            )
        else:
            location = _location(golden, name)
        with pytest.raises(OutsideSolarDomainError) as excinfo:
            compute_solar_events(location, _dt.date.fromisoformat(case["date"]))
        assert excinfo.value.reason == case["reason"]
