"""TCM organ clock, solar-anchored.

NOT covered by any 2026-07-22 decision -- see the open `organ-clock-anchor`
entry in docs-yaml/DECISIONS.yaml. The logic here is a verbatim port of the
behaviour calc.py already shipped: the DISC-UP day (sunrise -> sunset) divides
into the 6 day organs, the disc-down night (sunset -> next sunrise) into the 6
night organs, each organ into 5 qi phases. It deliberately does NOT use the
collared 125-mini tattva arcs; re-anchoring it would be inventing a decision.

One outright bug IS fixed in the move: calc.py's live path
(calculate_current_organ) computed the night as ``86400 - daylight`` while its
table path used ``next_sunrise - sunset``. Those disagree by the day-length
change over 24 h -- up to ~4 min near the equinoxes -- so the tray and the table
showed different organ boundaries. This module uses ``next_sunrise - sunset``
throughout. That is a bug fix, not a re-anchoring.

This is the only module that needs PyYAML, so the dependency is optional: a
consumer that wants the grid and the energy (astrolabe) never has to install it.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .solar import SolarEvents

ORGANS_PER_HALF = 6
PHASES_PER_ORGAN = 5

_DATA = Path(__file__).parent / "data" / "organs.yaml"


@dataclass(frozen=True, slots=True)
class OrganContent:
    qi_phases: tuple[str, ...]
    organs_day: tuple[str, ...]
    organs_night: tuple[str, ...]
    phases: dict[str, list[dict[str, str]]]


@dataclass(frozen=True, slots=True)
class OrganPhase:
    """One organ-phase span, with its content."""

    organ: str
    phase: str
    half: str                  # "day" | "night"
    organ_index: int           # 0..5
    phase_index: int           # 0..4
    organ_start: _dt.datetime
    organ_end: _dt.datetime
    start: _dt.datetime
    end: _dt.datetime
    organ_seconds: float
    phase_seconds: float
    pulse_position: str
    pulse_description: str
    activity: str
    improvement: str
    sound_practice: str
    inner_smile: str


@lru_cache(maxsize=1)
def load_organ_content() -> OrganContent:
    """Parse data/organs.yaml once per process."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on the env
        raise ImportError(
            "the organ clock needs PyYAML. Install the extra:\n"
            "    pip install 'tattva[organs]'"
        ) from exc

    raw = yaml.safe_load(_DATA.read_text(encoding="utf-8"))
    content = OrganContent(
        qi_phases=tuple(raw["qi_phases"]),
        organs_day=tuple(raw["organs_day"]),
        organs_night=tuple(raw["organs_night"]),
        phases=raw["organs"],
    )
    _validate(content)
    return content


def _validate(content: OrganContent) -> None:
    if len(content.qi_phases) != PHASES_PER_ORGAN:
        raise ValueError(f"expected {PHASES_PER_ORGAN} qi phases, got {len(content.qi_phases)}")
    for half, organs in (("day", content.organs_day), ("night", content.organs_night)):
        if len(organs) != ORGANS_PER_HALF:
            raise ValueError(f"expected {ORGANS_PER_HALF} {half} organs, got {len(organs)}")
        for organ in organs:
            entries = content.phases.get(organ)
            if entries is None:
                raise ValueError(f"organ {organ!r} missing from data")
            if len(entries) != PHASES_PER_ORGAN:
                raise ValueError(f"organ {organ!r} has {len(entries)} phases")
            for index, entry in enumerate(entries):
                for key in (
                    "phase", "activity", "improvement", "pulse_position",
                    "pulse_description", "sound_practice", "inner_smile",
                ):
                    if not entry.get(key):
                        raise ValueError(f"{organ}[{index}] missing {key!r}")


def _index_for(elapsed: float, span: float, count: int) -> int:
    """Which of ``count`` equal blocks of ``span`` seconds contains ``elapsed``.

    A plain ``elapsed // span`` is WRONG here, and subtly so -- the same class
    of bug already fixed in grid.py. Block starts are materialised through
    ``timedelta(seconds=...)``, which truncates to whole microseconds, so the
    reconstructed elapsed can land a hair BELOW an exact multiple. Flooring
    that puts the instant in the PREVIOUS block. Measured at phi=45.37642 on
    2026-06-21 before this fix: 5 of 18 dosha phase starts and 30 of 60 organ
    phase starts located to the wrong phase.

    Snapping to a boundary within a microsecond of one removes the class: a
    microsecond is the resolution datetime itself can represent, so nothing
    real is lost.
    """
    quotient = elapsed / span
    nearest = round(quotient)
    index = int(nearest) if abs(quotient - nearest) * span < 1e-6 else int(quotient // 1)
    return min(max(index, 0), count - 1)


def _half_for(when: _dt.datetime, solar: SolarEvents) -> tuple[str, _dt.datetime, float]:
    """Which half ``when`` falls in, with that half's start and duration."""
    if solar.sunrise <= when < solar.sunset:
        return "day", solar.sunrise, solar.day_seconds
    if when < solar.sunrise:
        # Tail of the previous night: it ends at this frame's sunrise.
        previous_sunset = solar.sunset - _dt.timedelta(seconds=solar.night_seconds)
        return "night", previous_sunset, solar.night_seconds
    return "night", solar.sunset, solar.night_seconds


def _build(
    half: str, half_start: _dt.datetime, half_seconds: float,
    organ_index: int, phase_index: int, content: OrganContent,
) -> OrganPhase:
    organs = content.organs_day if half == "day" else content.organs_night
    organ = organs[organ_index]
    entry = content.phases[organ][phase_index]

    organ_seconds = half_seconds / ORGANS_PER_HALF
    phase_seconds = organ_seconds / PHASES_PER_ORGAN
    organ_start = half_start + _dt.timedelta(seconds=organ_index * organ_seconds)
    start = organ_start + _dt.timedelta(seconds=phase_index * phase_seconds)

    return OrganPhase(
        organ=organ,
        phase=entry["phase"],
        half=half,
        organ_index=organ_index,
        phase_index=phase_index,
        organ_start=organ_start,
        organ_end=organ_start + _dt.timedelta(seconds=organ_seconds),
        start=start,
        end=start + _dt.timedelta(seconds=phase_seconds),
        organ_seconds=organ_seconds,
        phase_seconds=phase_seconds,
        pulse_position=entry["pulse_position"],
        pulse_description=entry["pulse_description"],
        activity=entry["activity"],
        improvement=entry["improvement"],
        sound_practice=entry["sound_practice"],
        inner_smile=entry["inner_smile"],
    )


def locate_organ_from_solar(when: _dt.datetime, solar: SolarEvents) -> OrganPhase:
    """The organ phase containing ``when``."""
    content = load_organ_content()
    half, half_start, half_seconds = _half_for(when, solar)

    organ_seconds = half_seconds / ORGANS_PER_HALF
    phase_seconds = organ_seconds / PHASES_PER_ORGAN
    elapsed = (when - half_start).total_seconds()

    organ_index = _index_for(elapsed, organ_seconds, ORGANS_PER_HALF)
    within = elapsed - organ_index * organ_seconds
    phase_index = _index_for(within, phase_seconds, PHASES_PER_ORGAN)

    return _build(half, half_start, half_seconds, organ_index, phase_index, content)


def generate_organ_table_from_solar(solar: SolarEvents) -> list[OrganPhase]:
    """All 60 organ phases (2 halves x 6 organs x 5 phases), chronological."""
    content = load_organ_content()
    out: list[OrganPhase] = []
    for half, half_start, half_seconds in (
        ("day", solar.sunrise, solar.day_seconds),
        ("night", solar.sunset, solar.night_seconds),
    ):
        for organ_index in range(ORGANS_PER_HALF):
            for phase_index in range(PHASES_PER_ORGAN):
                out.append(
                    _build(half, half_start, half_seconds, organ_index, phase_index, content)
                )
    return out
