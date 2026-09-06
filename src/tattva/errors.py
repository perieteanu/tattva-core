"""Typed errors for the solar tattva model.

The rule this package follows, borrowed from astrolabe's CircumpolarError
discipline: **the model raises, the presentation degrades.**

A time lookup outside the solar domain has no answer, so it must say so.
Drawing or displaying may degrade gracefully, but that decision belongs to the
caller -- never to this package, and never by inventing plausible numbers.
"""

from __future__ import annotations

import datetime as _dt
from typing import Literal

DomainFailure = Literal[
    "no_sunrise",      # astral found no rising crossing (polar night / midnight sun)
    "no_sunset",       # astral found no setting crossing
    "arc_disordered",  # events came back out of order (see class docstring)
    "arc_degenerate",  # an arc exists but is too short for a 125-mini grid
]


class OutsideSolarDomainError(ValueError):
    """The solar tattva grid is undefined here: day and night do not both exist.

    Per DECISIONS.yaml `division-anchor`, the solar tattva is defined ONLY where
    both a day arc and a night arc exist -- absolute bound the polar circle
    (~66.6 deg). Outside it the apps MUST raise and MUST NOT fabricate sun times.

    ``arc_disordered`` deserves special mention, because it is the failure mode
    that a naive ``try/except`` around astral does NOT catch. From latitude ~64
    deg upward at the solstice, astral searches within a single calendar day and
    returns a *setting* crossing that precedes the *rising* one -- for example at
    phi=66.0 on 2026-06-21 it gives set 21:35 before rise 22:51, and raises
    nothing. ``(sunset - sunrise)`` is then negative, ``mini_day`` is negative,
    and the collar arithmetic runs backwards to produce a silently inverted grid.
    Ordering must therefore be validated explicitly, not delegated to astral.

    Subclasses ValueError so that callers with an existing bare ``except
    ValueError`` keep working, while new code can catch the precise type.
    """

    def __init__(
        self,
        message: str,
        *,
        latitude_deg: float,
        longitude_deg: float,
        date: _dt.date,
        elevation_deg: float,
        reason: DomainFailure,
    ) -> None:
        super().__init__(message)
        self.latitude_deg = latitude_deg
        self.longitude_deg = longitude_deg
        self.date = date
        self.elevation_deg = elevation_deg
        self.reason: DomainFailure = reason

    def __str__(self) -> str:
        return (
            f"{super().__str__()} "
            f"[reason={self.reason}, phi={self.latitude_deg}, "
            f"lambda={self.longitude_deg}, date={self.date}, "
            f"theta={self.elevation_deg}]"
        )
