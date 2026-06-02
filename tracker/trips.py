"""
Trip detection state machine + Haversine helpers.

State transitions:
  IDLE  ──(movement detected)──► ACTIVE  ──(idle > timeout)──► IDLE
  ACTIVE updates the current trip's distance on every new point.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from . import config


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two WGS-84 coordinates."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_m(lat1, lng1, lat2, lng2) / 1000


@dataclass
class TripState:
    """Mutable state held by the daemon between polls."""

    # Currently open trip's DB id (None = no active trip)
    active_trip_id: Optional[int] = None

    # Last recorded GPS point
    last_lat: Optional[float] = None
    last_lng: Optional[float] = None
    last_point_time: Optional[datetime] = None

    # Accumulated distance for the active trip (km)
    distance_km: float = 0.0

    def is_active(self) -> bool:
        return self.active_trip_id is not None

    def timed_out(self, now: datetime) -> bool:
        """True if the last point was recorded more than TRIP_TIMEOUT_MINUTES ago."""
        if self.last_point_time is None:
            return False
        timeout = timedelta(minutes=config.TRIP_TIMEOUT_MINUTES)
        return (now - self.last_point_time) >= timeout

    def has_moved(self, lat: float, lng: float) -> bool:
        """True if the new position is at least MOVEMENT_THRESHOLD_METERS from the last."""
        if self.last_lat is None or self.last_lng is None:
            return True  # first point ever — treat as moved
        return haversine_m(self.last_lat, self.last_lng, lat, lng) >= config.MOVEMENT_THRESHOLD_METERS

    def advance(self, lat: float, lng: float) -> float:
        """Update position; return metres moved since last point."""
        if self.last_lat is not None and self.last_lng is not None:
            moved_m = haversine_m(self.last_lat, self.last_lng, lat, lng)
        else:
            moved_m = 0.0
        self.distance_km += moved_m / 1000
        self.last_lat = lat
        self.last_lng = lng
        return moved_m

    def reset(self) -> None:
        self.active_trip_id = None
        self.distance_km = 0.0
