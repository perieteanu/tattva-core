"""The 121/125 collar grid.

Implements DECISIONS.yaml `grid-phase`.

    mini_day   = (sunset - sunrise) / 121
    day arc    = [sunrise - 2*mini_day, sunset + 2*mini_day]   == 125 * mini_day
    night arc  = [day_arc.end, next_sunrise - 2*mini_day_TOMORROW]
    mini_night = night_arc_seconds / 125

The grid phase (A.A.Tejas starting exactly at geometric sunrise, P.P.Tejas
ending exactly at geometric sunset) is achieved BY CONSTRUCTION, not by an
index offset or a Tejas override. Mini 2 of the day arc starts at
``arc.start + 2*mini_day == sunrise``; mini 122 ends at
``arc.start + 123*mini_day == sunrise + 121*mini_day == sunset``.

The retired calc.py forced Tejas onto noon/midnight with an ``index_offset`` and
a +/-1 minute override that fabricated off-grid periods. Both are deleted: the
override was shown to be redundant (n=5 is odd and both arcs are symmetric about
the meridian, so the Tejas mega auto-centres), and under this construction it is
actively wrong.

CLOSING-COLLAR NOTE. The night arc's closing collar is 2 * TOMORROW's mini_day,
not today's. Decided 2026-09-04: it makes the arcs tile the timeline exactly --
tonight's night arc ends precisely where tomorrow's day arc begins. Using
today's mini on both ends would instead leave a gap or overlap of up to ~3 s
each day near the equinoxes (measured at Ramnicu Sarat: +3.175 s on 2026-03-20,
-3.048 s on 2026-09-04, ~0 at the solstices), so some instants would fall in two
arcs or in none. The cost is that the night arc is very slightly asymmetric
about its own midpoint; tiling was judged worth more.

FUTURE (`fractal-year-cycle`, curiosity-not-decided): everything below depends
on SolarEvents only through five instants and their ordering. If the year rung
is ever decided, extract a Protocol over those members and let a YearEvents
(equinox/solstice/equinox/solstice/next-equinox) satisfy it -- the arithmetic
here would not change. No speculative abstraction is written today.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Literal

from .solar import SolarEvents

TATTVAS: tuple[str, ...] = ("Akasha", "Vayu", "Tejas", "Apas", "Prithivi")

LIT_MINIS = 121      # the disc-up day, per `grid-phase`.boundary_convention
ARC_MINIS = 125      # 5*5*5
COLLAR_MINIS = 2     # (125 - 121) / 2, symmetric each end -- DERIVED, not chosen

# An instant within this distance of a solar event is flagged for display.
# Same 60 s semantics the retired code used in five copy-pasted places.
SPECIAL_WINDOW_SECONDS = 60.0

ArcKind = Literal["day", "night"]


@dataclass(frozen=True, slots=True)
class Arc:
    """One 125-mini arc."""

    kind: ArcKind
    start: _dt.datetime
    end: _dt.datetime
    mini_seconds: float

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()


@dataclass(frozen=True, slots=True)
class Grid:
    """The day arc, the night arc, and the solar frame they came from."""

    day: Arc
    night: Arc
    solar: SolarEvents

    def arc_for(self, when: _dt.datetime) -> Arc | None:
        if self.day.start <= when < self.day.end:
            return self.day
        if self.night.start <= when < self.night.end:
            return self.night
        return None


@dataclass(frozen=True, slots=True)
class Position:
    """Where one instant falls in the grid, at all three levels."""

    arc: ArcKind
    ordinal: int          # 0..124 within the arc
    mega_index: int
    tattva_index: int
    mini_index: int
    mega: str
    tattva: str
    mini: str
    mega_start: _dt.datetime
    mega_end: _dt.datetime
    tattva_start: _dt.datetime
    tattva_end: _dt.datetime
    mini_start: _dt.datetime
    mini_end: _dt.datetime
    mega_seconds: float
    tattva_seconds: float
    mini_seconds: float
    is_special: bool

    # True for the 2 minis at each end of an arc that fall OUTSIDE the disc-up
    # day (or the disc-down night): the twilight collar. On the day arc these
    # are A.A.Akasha / A.A.Vayu before sunrise and P.P.Apas / P.P.Prithivi after
    # sunset. The collar is a DERIVED consequence of the element grid, not a
    # chosen twilight angle -- see DECISIONS `grid-phase`.boundary_convention.
    is_collar: bool


def _offset(base: _dt.datetime, seconds: float) -> _dt.datetime:
    return base + _dt.timedelta(seconds=seconds)


def build_grid_from_solar(solar: SolarEvents) -> Grid:
    """The two arcs for one day-night cycle."""
    mini_day = solar.day_seconds / LIT_MINIS
    next_mini_day = solar.next_day_seconds / LIT_MINIS

    day_start = _offset(solar.sunrise, -COLLAR_MINIS * mini_day)
    day_end = _offset(solar.sunset, COLLAR_MINIS * mini_day)

    night_start = day_end
    night_end = _offset(solar.next_sunrise, -COLLAR_MINIS * next_mini_day)
    mini_night = (night_end - night_start).total_seconds() / ARC_MINIS

    return Grid(
        day=Arc(kind="day", start=day_start, end=day_end, mini_seconds=mini_day),
        night=Arc(kind="night", start=night_start, end=night_end, mini_seconds=mini_night),
        solar=solar,
    )


def _is_special(when: _dt.datetime, solar: SolarEvents) -> bool:
    """Within 60 s of a solar event. One helper; the retired code had five copies."""
    events = (solar.sunrise, solar.noon, solar.sunset, solar.midnight, solar.next_sunrise)
    return any(abs((when - event).total_seconds()) < SPECIAL_WINDOW_SECONDS for event in events)


def position_at_ordinal(ordinal: int, arc: Arc, solar: SolarEvents) -> Position:
    """The Position for mini ``ordinal`` (0..124) of ``arc``.

    Starts are computed as ``arc.start + k * mini_seconds`` -- one multiplication
    from the arc base, never accumulated by repeated addition. The retired nested
    -loop form was algebraically equal but numerically noisier; the flat form is
    what makes 1e-9 test tolerances achievable.
    """
    if not 0 <= ordinal < ARC_MINIS:
        raise ValueError(f"ordinal out of range: {ordinal}")

    mega_index = ordinal // 25
    tattva_index = (ordinal // 5) % 5
    mini_index = ordinal % 5

    mini_seconds = arc.mini_seconds
    tattva_seconds = mini_seconds * 5
    mega_seconds = mini_seconds * 25

    mini_start = _offset(arc.start, ordinal * mini_seconds)
    tattva_start = _offset(arc.start, (ordinal // 5) * tattva_seconds)
    mega_start = _offset(arc.start, mega_index * mega_seconds)

    return Position(
        arc=arc.kind,
        ordinal=ordinal,
        mega_index=mega_index,
        tattva_index=tattva_index,
        mini_index=mini_index,
        mega=TATTVAS[mega_index],
        tattva=TATTVAS[tattva_index],
        mini=TATTVAS[mini_index],
        mega_start=mega_start,
        mega_end=_offset(mega_start, mega_seconds),
        tattva_start=tattva_start,
        tattva_end=_offset(tattva_start, tattva_seconds),
        mini_start=mini_start,
        mini_end=_offset(mini_start, mini_seconds),
        mega_seconds=mega_seconds,
        tattva_seconds=tattva_seconds,
        mini_seconds=mini_seconds,
        is_special=_is_special(mini_start, solar),
        is_collar=(ordinal < COLLAR_MINIS or ordinal >= ARC_MINIS - COLLAR_MINIS),
    )


def _ordinal_for(when: _dt.datetime, arc: Arc) -> int:
    """Which mini (0..124) of ``arc`` contains ``when``.

    A plain ``elapsed // mini_seconds`` is WRONG here, and subtly so. Mini
    starts are materialised as ``timedelta(seconds=k * mini_seconds)``, which
    truncates to whole microseconds, so the reconstructed elapsed can land a
    hair BELOW ``k * mini_seconds`` -- about 1e-9 of a mini. Flooring that puts
    the instant in mini k-1. Measured at Ramnicu Sarat on 2026-06-21, 57 of the
    125 day-arc boundaries flipped that way when queried at their own start.

    Snapping to a boundary within a microsecond of one removes the whole class:
    a microsecond is the resolution datetime itself can represent, so nothing
    real is lost, and every mini_start reliably locates to its own mini.
    """
    elapsed = (when - arc.start).total_seconds()
    quotient = elapsed / arc.mini_seconds
    nearest = round(quotient)
    if abs(quotient - nearest) * arc.mini_seconds < 1e-6:
        ordinal = int(nearest)
    else:
        ordinal = int(quotient // 1)
    return min(max(ordinal, 0), ARC_MINIS - 1)


def locate_from_grid(when: _dt.datetime, grid: Grid) -> Position:
    """THE locate function. Both the table and the live path go through it.

    One integer -- ``ordinal`` -- determines all three levels by pure integer
    arithmetic. The Java engine derives the indices twice (once building the
    table, once for the live position) and the two can disagree at boundaries
    under floating point; here divergence is structurally impossible.
    """
    arc = grid.arc_for(when)
    if arc is None:
        raise ValueError(
            f"{when.isoformat()} lies outside this grid "
            f"({grid.day.start.isoformat()} .. {grid.night.end.isoformat()}); "
            "the caller built the grid for the wrong day"
        )

    ordinal = _ordinal_for(when, arc)
    return position_at_ordinal(ordinal, arc, grid.solar)


def generate_table_from_grid(grid: Grid) -> list[Position]:
    """All 250 minis (125 day + 125 night), chronological."""
    return [
        position_at_ordinal(ordinal, arc, grid.solar)
        for arc in (grid.day, grid.night)
        for ordinal in range(ARC_MINIS)
    ]


def build_grid(
    location, day: _dt.date, *, elevation_deg: float | None = None
) -> Grid:
    """Convenience: compute the solar frame for ``day``, then build the grid."""
    from .solar import UPPER_LIMB_DEG, compute_solar_events

    if elevation_deg is None:
        elevation_deg = UPPER_LIMB_DEG
    return build_grid_from_solar(compute_solar_events(location, day, elevation_deg=elevation_deg))


def generate_table(
    location, day: _dt.date, *, elevation_deg: float | None = None
) -> list[Position]:
    """Convenience: the 250-mini table for ``day`` at ``location``."""
    return generate_table_from_grid(build_grid(location, day, elevation_deg=elevation_deg))


def locate(when: _dt.datetime, location, *, elevation_deg: float | None = None) -> Position:
    """Locate ``when``, choosing the correct day's grid automatically.

    An instant just after local midnight belongs to the PREVIOUS calendar day's
    night arc, so this tries that day first and steps forward as needed. This is
    the wrapper the tray uses; it is the reason a live display never has to
    reason about which day's frame it is in.
    """
    local_day = when.astimezone(location.tzinfo).date()
    for candidate in (local_day - _dt.timedelta(days=1), local_day):
        grid = build_grid(location, candidate, elevation_deg=elevation_deg)
        if grid.arc_for(when) is not None:
            return locate_from_grid(when, grid)
    raise ValueError(f"{when.isoformat()} could not be placed in any adjacent grid")
