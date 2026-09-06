#!/usr/bin/env python3
"""Generate tests/fixtures/golden_model.json.

Run with any interpreter that has the package installed:

    ~/.pyenv/versions/astrolabe/bin/python tests/make_golden.py

Locations and dates deliberately match astrolabe's make_fixtures.py so the two
projects' fixtures are directly comparable. Unlike every earlier fixture in this
family, this one records the UNDEFINED cases too -- the polar latitudes where
the model must raise -- with the expected reason, so the Android port has
something concrete to match when it implements its own typed error.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tattva import (  # noqa: E402
    UPPER_LIMB_DEG,
    OutsideSolarDomainError,
    build_grid,
    compute_energy_from_solar,
    compute_solar_events,
    generate_table_from_grid,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import BUENOS_AIRES, DATES, QUITO, RAMNICU_SARAT, TROMSO  # noqa: E402

ENERGY_STEP_MINUTES = 30
OUT = Path(__file__).resolve().parent / "fixtures" / "golden_model.json"


def iso(value: _dt.datetime) -> str:
    return value.isoformat()


def main() -> None:
    payload: dict = {
        "_note": (
            "Golden fixture for the tattva model. Anchor is geometric upper limb "
            "theta=-0.267 (DECISIONS division-anchor / grid-phase); energy is the "
            "four-point cosine (energy-four-point); midnight is the night midpoint "
            "(midnight-definition). Regenerate with tests/make_golden.py."
        ),
        "generated_by": "tests/make_golden.py",
        "elevation_deg": UPPER_LIMB_DEG,
        "lit_minis": 121,
        "arc_minis": 125,
        "energy_step_minutes": ENERGY_STEP_MINUTES,
        "locations": {},
        "solar": [],
        "energy": [],
        "tables": [],
        "undefined": [],
    }

    for location in (RAMNICU_SARAT, BUENOS_AIRES, QUITO, TROMSO):
        payload["locations"][location.name] = {
            "latitude_deg": location.latitude_deg,
            "longitude_deg": location.longitude_deg,
            "timezone": location.timezone,
        }

    for location in (RAMNICU_SARAT, BUENOS_AIRES, QUITO):
        for day in DATES:
            grid = build_grid(location, day)
            solar = grid.solar
            payload["solar"].append({
                "location": location.name,
                "date": day.isoformat(),
                "sunrise": iso(solar.sunrise),
                "noon": iso(solar.noon),
                "sunset": iso(solar.sunset),
                "next_sunrise": iso(solar.next_sunrise),
                "next_sunset": iso(solar.next_sunset),
                "midnight": iso(solar.midnight),
                "day_seconds": solar.day_seconds,
                "night_seconds": solar.night_seconds,
            })

            cursor = solar.sunrise
            while cursor < solar.next_sunrise:
                energy = compute_energy_from_solar(cursor, solar)
                payload["energy"].append({
                    "location": location.name,
                    "date": day.isoformat(),
                    "time": iso(cursor),
                    "yang": energy.yang,
                    "yin": energy.yin,
                    "yang_dir": energy.yang_dir,
                    "yin_dir": energy.yin_dir,
                    "segment": energy.segment,
                })
                cursor += _dt.timedelta(minutes=ENERGY_STEP_MINUTES)

            payload["tables"].append({
                "location": location.name,
                "date": day.isoformat(),
                "day_arc": [iso(grid.day.start), iso(grid.day.end), grid.day.mini_seconds],
                "night_arc": [iso(grid.night.start), iso(grid.night.end), grid.night.mini_seconds],
                "periods": [
                    {
                        "arc": row.arc,
                        "ordinal": row.ordinal,
                        "time": iso(row.mini_start),
                        "mega_tattva": row.mega,
                        "tattva": row.tattva,
                        "mini_tattva": row.mini,
                        "mini_seconds": row.mini_seconds,
                        "is_special": row.is_special,
                    }
                    for row in generate_table_from_grid(grid)
                ],
            })

    for location in (TROMSO,):
        for day in (_dt.date(2026, 6, 21), _dt.date(2026, 12, 21)):
            try:
                compute_solar_events(location, day)
            except OutsideSolarDomainError as exc:
                payload["undefined"].append({
                    "location": location.name,
                    "date": day.isoformat(),
                    "reason": exc.reason,
                })
            else:  # pragma: no cover
                raise SystemExit(f"expected {location.name} {day} to be undefined")

    for latitude in (64.0, 66.0):
        probe = type(RAMNICU_SARAT)("Edge", "Test", latitude, 27.05, "Europe/Bucharest")
        try:
            compute_solar_events(probe, _dt.date(2026, 6, 21))
        except OutsideSolarDomainError as exc:
            payload["undefined"].append({
                "location": f"Edge {latitude}",
                "date": "2026-06-21",
                "reason": exc.reason,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  solar {len(payload['solar'])}, energy {len(payload['energy'])}, "
          f"tables {len(payload['tables'])}, undefined {len(payload['undefined'])}")


if __name__ == "__main__":
    main()
