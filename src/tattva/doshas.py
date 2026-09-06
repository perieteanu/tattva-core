"""Ayurvedic dosha clock, solar-anchored.

Implements DECISIONS.yaml `dosha-clock`.

AUTHORSHIP, NOT DOCTRINE. Classical Ayurveda gives doshas as CLOCK HOURS --
Kapha ~06-10, Pitta ~10-14, Vata ~14-18, repeating at night, in six fixed
4-hour blocks. Anchoring them to the sun instead, and letting day and night
blocks differ in length, is a deliberate departure. The tradition also names no
sub-phases at all, so the 3-fold Rising/Peak/Declining subdivision is authorship
too. Both are recorded as such in DECISIONS; do not present them as classical.

The day arc (sunrise -> sunset) divides into 3 EQUAL doshas; the night arc
(sunset -> next sunrise) into its own 3. Order is Kapha -> Pitta -> Vata,
CONTINUING across the sunset boundary -- with 3 doshas in 3 slots the cycle
wraps exactly, so "continue" and "repeat" coincide here.

Anchored on the DISC-UP day, like the organ clock and unlike the tattva grid --
no collar, no 121/125, no minis. See `organ-clock-anchor` for why other systems
do not inherit the tattva collar.

DERIVED, NOT IMPOSED: Pitta always spans solar midnight and Vata always runs
pre-dawn, matching the classical night pattern. That falls out of the
arithmetic -- the middle of three equal blocks contains the arc's midpoint, and
by `midnight-definition` the night arc's midpoint IS solar midnight. Same odd-n
symmetry that auto-centres the Tejas mega.

This module deliberately MIRRORS organs.py rather than sharing an abstraction
with it. `fractal-year-cycle` notes that a generic engine parameterised on N is
the eventual refactor, and doshas being the third caller (tattvas 5, organs 6,
doshas 3) is the evidence for it -- but abstracting mid-split would risk the
test baseline for no delivery benefit.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .solar import SolarEvents

DOSHAS_PER_HALF = 3
PHASES_PER_DOSHA = 3

_DATA = Path(__file__).parent / "data" / "doshas.yaml"


@dataclass(frozen=True, slots=True)
class DoshaContent:
    doshas: tuple[str, ...]
    phases: tuple[str, ...]
    entries: dict[str, dict[str, str]]


@dataclass(frozen=True, slots=True)
class DoshaPeriod:
    """One dosha-phase span, with the dosha's content."""

    dosha: str
    phase: str
    half: str                 # "day" | "night"
    dosha_index: int          # 0..2
    phase_index: int          # 0..2
    dosha_start: _dt.datetime
    dosha_end: _dt.datetime
    start: _dt.datetime
    end: _dt.datetime
    dosha_seconds: float
    phase_seconds: float
    qualities: str
    signs: str
    favourable: str
    avoid: str


@lru_cache(maxsize=1)
def load_dosha_content() -> DoshaContent:
    """Parse data/doshas.yaml once per process."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on the env
        raise ImportError(
            "the dosha clock needs PyYAML. Install the extra:\n"
            "    pip install 'tattva[doshas]'"
        ) from exc

    raw = yaml.safe_load(_DATA.read_text(encoding="utf-8"))
    content = DoshaContent(
        doshas=tuple(raw["doshas"]),
        phases=tuple(raw["phases"]),
        entries=raw["entries"],
    )
    _validate(content)
    return content


def _validate(content: DoshaContent) -> None:
    if len(content.doshas) != DOSHAS_PER_HALF:
        raise ValueError(f"expected {DOSHAS_PER_HALF} doshas, got {len(content.doshas)}")
    if len(content.phases) != PHASES_PER_DOSHA:
        raise ValueError(f"expected {PHASES_PER_DOSHA} phases, got {len(content.phases)}")
    for dosha in content.doshas:
        entry = content.entries.get(dosha)
        if entry is None:
            raise ValueError(f"dosha {dosha!r} missing from data")
        for key in ("qualities", "signs", "favourable", "avoid"):
            if not entry.get(key):
                raise ValueError(f"{dosha} missing {key!r}")


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
    dosha_index: int, phase_index: int, content: DoshaContent,
) -> DoshaPeriod:
    dosha = content.doshas[dosha_index]
    entry = content.entries[dosha]

    dosha_seconds = half_seconds / DOSHAS_PER_HALF
    phase_seconds = dosha_seconds / PHASES_PER_DOSHA
    dosha_start = half_start + _dt.timedelta(seconds=dosha_index * dosha_seconds)
    start = dosha_start + _dt.timedelta(seconds=phase_index * phase_seconds)

    return DoshaPeriod(
        dosha=dosha,
        phase=content.phases[phase_index],
        half=half,
        dosha_index=dosha_index,
        phase_index=phase_index,
        dosha_start=dosha_start,
        dosha_end=dosha_start + _dt.timedelta(seconds=dosha_seconds),
        start=start,
        end=start + _dt.timedelta(seconds=phase_seconds),
        dosha_seconds=dosha_seconds,
        phase_seconds=phase_seconds,
        qualities=entry["qualities"],
        signs=entry["signs"],
        favourable=entry["favourable"],
        avoid=entry["avoid"],
    )


def locate_dosha_from_solar(when: _dt.datetime, solar: SolarEvents) -> DoshaPeriod:
    """The dosha phase containing ``when``."""
    content = load_dosha_content()
    half, half_start, half_seconds = _half_for(when, solar)

    dosha_seconds = half_seconds / DOSHAS_PER_HALF
    phase_seconds = dosha_seconds / PHASES_PER_DOSHA
    elapsed = (when - half_start).total_seconds()

    dosha_index = _index_for(elapsed, dosha_seconds, DOSHAS_PER_HALF)
    within = elapsed - dosha_index * dosha_seconds
    phase_index = _index_for(within, phase_seconds, PHASES_PER_DOSHA)

    return _build(half, half_start, half_seconds, dosha_index, phase_index, content)


def generate_dosha_table_from_solar(solar: SolarEvents) -> list[DoshaPeriod]:
    """All 18 dosha phases (2 halves x 3 doshas x 3 phases), chronological."""
    content = load_dosha_content()
    out: list[DoshaPeriod] = []
    for half, half_start, half_seconds in (
        ("day", solar.sunrise, solar.day_seconds),
        ("night", solar.sunset, solar.night_seconds),
    ):
        for dosha_index in range(DOSHAS_PER_HALF):
            for phase_index in range(PHASES_PER_DOSHA):
                out.append(
                    _build(half, half_start, half_seconds, dosha_index, phase_index, content)
                )
    return out
