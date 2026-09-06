# tattva-core

Solar cycle model: geometric-sunrise division, the 121/125 collar grid, four-point cosine energy, TCM organ and Ayurvedic dosha clocks.

Pure Python, no GUI. `astral` is the only runtime dependency; PyYAML is needed
only for the organ and dosha content.

## The model

- **Anchor** — geometric sunrise, upper limb at the true horizon (θ = −0.267°).
  Not refracted, not civil twilight. A depression angle is a convention; a
  geometric crossing is not.
- **Tattva grid** — the disc-up day is 121 minis; the full day arc is 125,
  adding a two-mini twilight collar at each end, so `Akasha.Akasha.Tejas`
  begins exactly at sunrise.
- **Energy** — a four-point cosine: yin peaks at solar midnight, yang at noon,
  crossing 50/50 at sunrise and sunset.
- **Midnight** — the midpoint of the disc-down night, so the element grid and
  the energy curve share one definition.
- **Domain** — defined only where the sun both rises and sets. Outside that it
  raises `OutsideSolarDomainError` and never fabricates times.

```python
from datetime import date
from tattva import Location, build_grid, compute_energy_from_solar, locate_from_grid

place = Location("Bucharest", "Romania", 44.4268, 26.1025, "Europe/Bucharest")
grid = build_grid(place, date(2026, 9, 6))

position = locate_from_grid(when, grid)          # mega / tattva / mini
energy = compute_energy_from_solar(when, grid.solar)
```

Also included: a TCM organ clock (`tattva.organs`) and an Ayurvedic dosha clock
(`tattva.doshas`), both dividing the disc-up day rather than the collared arcs.
Their solar anchoring is a deliberate departure from the traditional clock-hour
schemes — authorship, not doctrine.

## Install and test

```bash
pip install -e .
pip install -e '.[content]'    # organ and dosha clocks
pytest -q
```

## Licence

GPL-3.0-or-later. Copyright (C) 2026 Perieteanu Costin.

## Credits

Developed by Perieteanu Costin in collaboration with Claude (Anthropic's Claude Code).
