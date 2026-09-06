"""Solar events: the geometric anchor instants of one day-night cycle.

Implements DECISIONS.yaml `division-anchor` and `midnight-definition`.

The anchor is a GEOMETRIC crossing -- the Sun's disc against the true horizon,
with no refraction model and no scattering threshold. Per `division-anchor`,
every depression-angle "dawn" (-6 / -12 / -18) is a level-set a human picked on
a smooth brightness curve, i.e. a convention; the only convention-free instants
are geometric crossings, whose author is celestial mechanics.

Default anchor is the upper-limb variant, theta = -0.267 deg (`grid-phase`
anchor_variant): still pure geometry, being the Sun's own angular semidiameter.

IMPLEMENTATION TRAP -- do not "simplify" this to astral's sun() or to a zenith
table. astral's sun() applies refraction, giving an effective h0 of -0.789107
deg, not the geometric 0. And a zenith-based helper of the shape
``-(zenith - 90) - refraction_at_zenith(zenith)`` returns -0.481944 for zenith
90.0, NOT 0.0, because it always subtracts refraction. The correct primitive is
``time_at_elevation(..., with_refraction=False)``, which is what this module uses.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from astral import SunDirection
from astral.sun import noon as _astral_noon
from astral.sun import time_at_elevation

from .errors import OutsideSolarDomainError
from .location import Location

# The Sun's centre at the true (astronomical) horizon. The zero-assumption primitive.
GEOMETRIC_CENTRE_DEG = 0.0

# Upper limb at the horizon: "the disc first peeks". The value is the Sun's real
# angular semidiameter. Per `grid-phase`.anchor_variant the fixed 0.267 is within
# ~1-2 s of the true per-date semidiameter (0.263 at July aphelion .. 0.272 at
# January perihelion), which is immaterial in practice.
UPPER_LIMB_DEG = -0.267

# An arc shorter than this cannot carry a meaningful 125-mini grid (minis would
# be sub-second). 125 s => 1 s per mini.
_MIN_ARC_SECONDS = 125.0


@dataclass(frozen=True)
class SolarEvents:
    """The anchor instants for one day-night cycle at one place.

    All instants are geometric crossings at ``elevation_deg`` (no refraction),
    except ``noon``, which is the upper solar transit, and ``midnight``, which is
    a construction -- see below.

    There is deliberately NO ``dawn`` / ``dusk`` / ``next_dawn``. Those fields
    exist in the older six-point model only to carry civil twilight, which
    `division-anchor` rejects as an anchor and `energy-four-point` no longer
    needs. Omitting them makes regression to a twilight anchor structurally
    impossible rather than merely discouraged.

    ``next_sunset`` is carried because the night arc's closing collar is measured
    in TOMORROW's mini_day -- see grid.py.
    """

    sunrise: _dt.datetime
    noon: _dt.datetime
    sunset: _dt.datetime
    next_sunrise: _dt.datetime
    next_sunset: _dt.datetime
    elevation_deg: float
    latitude_deg: float
    longitude_deg: float
    date: _dt.date

    def __post_init__(self) -> None:
        """The domain gate.

        Every construction path goes through here -- including a test building
        one by hand from a fixture -- so an invalid grid cannot be obtained.
        """
        self._require_ordered(self.sunrise, self.sunset, "sunset precedes sunrise")
        self._require_ordered(self.sunset, self.next_sunrise, "next sunrise precedes sunset")
        self._require_ordered(
            self.next_sunrise, self.next_sunset, "next sunset precedes next sunrise"
        )

        if self.day_seconds < _MIN_ARC_SECONDS:
            self._fail(
                f"day arc too short for a 125-mini grid: {self.day_seconds:.3f} s",
                "arc_degenerate",
            )
        if self.night_seconds < _MIN_ARC_SECONDS:
            self._fail(
                f"night arc too short for a 125-mini grid: {self.night_seconds:.3f} s",
                "arc_degenerate",
            )

    def _require_ordered(self, first: _dt.datetime, second: _dt.datetime, what: str) -> None:
        if second <= first:
            self._fail(
                f"{what} ({first.isoformat()} .. {second.isoformat()}); "
                "the sun does not both rise and set here on this date",
                "arc_disordered",
            )

    def _fail(self, message: str, reason) -> None:
        raise OutsideSolarDomainError(
            message,
            latitude_deg=self.latitude_deg,
            longitude_deg=self.longitude_deg,
            date=self.date,
            elevation_deg=self.elevation_deg,
            reason=reason,
        )

    # -- derived quantities -------------------------------------------------

    @property
    def midnight(self) -> _dt.datetime:
        """Solar midnight per `midnight-definition`: the time MIDPOINT of the
        disc-down night, ``(sunset + next_sunrise) / 2``.

        NOT ``noon + 12h`` (which calc.py used in six places, wrong by -28..+40 s
        with a seasonal sign flip) and NOT the true lower transit (which differs
        by ~15 s). Costin chose the midpoint so that elements and energy share ONE
        midnight -- the Tejas night-arc centre and the four-point yin peak are the
        same instant, by construction.
        """
        return self.sunset + (self.next_sunrise - self.sunset) / 2

    @property
    def day_seconds(self) -> float:
        """The disc-up day: sunrise to sunset."""
        return (self.sunset - self.sunrise).total_seconds()

    @property
    def night_seconds(self) -> float:
        """The disc-down night: sunset to next sunrise."""
        return (self.next_sunrise - self.sunset).total_seconds()

    @property
    def next_day_seconds(self) -> float:
        """Tomorrow's disc-up day. Needed for the night arc's closing collar."""
        return (self.next_sunset - self.next_sunrise).total_seconds()


def _crossing(
    location: Location,
    day: _dt.date,
    elevation_deg: float,
    direction: SunDirection,
    what: str,
) -> _dt.datetime:
    """One geometric crossing, or OutsideSolarDomainError.

    astral raises a bare ValueError ("Sun never reaches an elevation of ...")
    when there is no crossing; that is translated into the typed error here.
    Note this is necessary but NOT sufficient -- see SolarEvents.__post_init__,
    which catches the disordered case astral does not report at all.
    """
    try:
        return time_at_elevation(
            location.observer,
            elevation_deg,
            date=day,
            direction=direction,
            tzinfo=location.tzinfo,
            with_refraction=False,
        )
    except ValueError as exc:
        raise OutsideSolarDomainError(
            f"astral found no {what} at theta={elevation_deg} on {day}: {exc}",
            latitude_deg=location.latitude_deg,
            longitude_deg=location.longitude_deg,
            date=day,
            elevation_deg=elevation_deg,
            reason="no_sunrise" if direction is SunDirection.RISING else "no_sunset",
        ) from exc


def compute_solar_events(
    location: Location,
    day: _dt.date,
    *,
    elevation_deg: float = UPPER_LIMB_DEG,
) -> SolarEvents:
    """Geometric solar events for ``day`` at ``location``.

    Raises OutsideSolarDomainError outside the solar domain (~66.6 deg), where
    the sun does not both rise and set. Never fabricates.
    """
    tomorrow = day + _dt.timedelta(days=1)
    return SolarEvents(
        sunrise=_crossing(location, day, elevation_deg, SunDirection.RISING, "sunrise"),
        noon=_astral_noon(location.observer, date=day, tzinfo=location.tzinfo),
        sunset=_crossing(location, day, elevation_deg, SunDirection.SETTING, "sunset"),
        next_sunrise=_crossing(
            location, tomorrow, elevation_deg, SunDirection.RISING, "next sunrise"
        ),
        next_sunset=_crossing(
            location, tomorrow, elevation_deg, SunDirection.SETTING, "next sunset"
        ),
        elevation_deg=elevation_deg,
        latitude_deg=location.latitude_deg,
        longitude_deg=location.longitude_deg,
        date=day,
    )
