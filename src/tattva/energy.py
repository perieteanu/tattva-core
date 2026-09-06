"""Four-point cosine yin/yang energy.

Implements DECISIONS.yaml `energy-four-point`, which supersedes the six-point
twilight model of `energy-model` (2026-07-12).

    Midnight (yin 100%)  -> Sunrise : yin 100% -> 50%
    Sunrise  (50/50)     -> Noon    : yang 50% -> 100%
    Noon     (yang 100%) -> Sunset  : yang 100% -> 50%
    Sunset   (50/50)     -> Midnight: yin 50% -> 100%

Daily-renormalised: every day reaches full yang at noon and full yin at
midnight, regardless of season. The physical alternative (season-varying
extremes) was considered and rejected -- it breaks the daily renormalisation the
tattva/svara cycle assumes.

Why four points and not six: the six-point model existed only to give the
sunrise/sunset neighbourhood special treatment via its 70% civil-twilight
shoulders. That specialness has MOVED into the element grid (Tejas ignites at
the disc; the twilight-collar minis). With civil twilight rejected as an anchor,
the shoulders have nothing to attach to. Note the 50/50 crossings were ALWAYS at
sunrise/sunset even in the six-point model -- only the shoulders are dropped.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass
from typing import Literal

from .solar import SolarEvents

Segment = Literal[
    "midnight_to_sunrise",
    "sunrise_to_noon",
    "noon_to_sunset",
    "sunset_to_midnight",
]

RISING = "^"
FALLING = "v"


@dataclass(frozen=True, slots=True)
class Energy:
    """Yang/yin at one instant. ``yang + yin == 1.0`` always."""

    yang: float
    yin: float
    yang_dir: str
    yin_dir: str
    segment: Segment


def _ease(p: float) -> float:
    """Cosine easing, 0 -> 1, with zero derivative at both ends.

    This is what makes the curve smooth (flat-tangent) at every anchor, rather
    than the piecewise-linear kinks of the retired model in calc.py.
    """
    return (1.0 - math.cos(p * math.pi)) / 2.0


def compute_energy_from_solar(when: _dt.datetime, solar: SolarEvents) -> Energy:
    """Yang/yin for ``when``, given a day's solar frame.

    ``when`` may fall anywhere in the cycle; the segment is selected by
    comparison against the frame's anchors. Instants before this frame's sunrise
    are handled by the previous night's descending-yin branch, which is why the
    yin peak is reached from both sides without a wrap-around special case.
    """
    yang_dir = RISING
    segment: Segment

    if when < solar.sunrise:
        # Pre-dawn: the tail of the previous night. Yin falls 100% -> 50% as
        # sunrise approaches. The previous midnight is one night-length back.
        previous_midnight = solar.midnight - _dt.timedelta(seconds=solar.night_seconds)
        span = (solar.sunrise - previous_midnight).total_seconds()
        progress = (when - previous_midnight).total_seconds() / span
        yin = 1.0 - 0.5 * _ease(progress)
        segment = "midnight_to_sunrise"
        yang_dir = RISING
    elif when < solar.noon:
        span = (solar.noon - solar.sunrise).total_seconds()
        progress = (when - solar.sunrise).total_seconds() / span
        yin = 0.5 - 0.5 * _ease(progress)
        segment = "sunrise_to_noon"
        yang_dir = RISING
    elif when < solar.sunset:
        span = (solar.sunset - solar.noon).total_seconds()
        progress = (when - solar.noon).total_seconds() / span
        yin = 0.5 * _ease(progress)
        segment = "noon_to_sunset"
        yang_dir = FALLING
    elif when < solar.midnight:
        span = (solar.midnight - solar.sunset).total_seconds()
        progress = (when - solar.sunset).total_seconds() / span
        yin = 0.5 + 0.5 * _ease(progress)
        segment = "sunset_to_midnight"
        yang_dir = FALLING
    else:
        # Post-midnight: yin falls back toward the next sunrise's 50/50.
        span = (solar.next_sunrise - solar.midnight).total_seconds()
        progress = (when - solar.midnight).total_seconds() / span
        yin = 1.0 - 0.5 * _ease(progress)
        segment = "midnight_to_sunrise"
        yang_dir = RISING

    # Clamp ONCE, then derive the complement. The retired calc.py computed
    # `yang = 1 - yin` BEFORE clamping each independently, so when its progress
    # went negative (it used today's sunrise with a next-day midnight) both
    # clamped to their own bounds and the invariant broke -- the tray showed
    # 100% yang / 0% yin from local midnight to sunrise. Deriving after the
    # clamp makes that failure unrepresentable.
    yin = max(0.0, min(1.0, yin))
    yang = 1.0 - yin

    return Energy(
        yang=yang,
        yin=yin,
        yang_dir=yang_dir,
        yin_dir=FALLING if yang_dir == RISING else RISING,
        segment=segment,
    )
