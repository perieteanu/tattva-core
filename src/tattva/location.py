"""Location: an immutable, validated place on Earth.

Deliberately NOT astral's LocationInfo. Its positional argument order is
already a live footgun in this codebase: one consumer builds it with keywords
(dump_golden.py) while another passes positionally in a different order
(astrolabe's make_fixtures.py, as ``LocationInfo(name, region, tz, lat, lon)``).
Two conventions for one constructor is a silent lat/lon swap waiting to happen.
A frozen dataclass with ``_deg`` suffixes ends that.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astral import Observer


@dataclass(frozen=True)
class Location:
    """A named place. Angles in degrees; timezone as an IANA name."""

    name: str
    region: str
    latitude_deg: float
    longitude_deg: float
    timezone: str

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(f"latitude_deg out of range: {self.latitude_deg}")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError(f"longitude_deg out of range: {self.longitude_deg}")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone: {self.timezone!r}") from exc

    @cached_property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @cached_property
    def observer(self) -> Observer:
        """astral Observer. Elevation is deliberately absent: the model is
        geometric, and an observer elevation would reintroduce a horizon dip
        that the geometric anchor exists to avoid."""
        return Observer(latitude=self.latitude_deg, longitude=self.longitude_deg)
