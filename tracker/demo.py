"""
Demo mode — fake vehicle data and pre-seeded trips so the UI can be explored
without real FordPass credentials.

Routes are set in Austin, TX. Each trip is a short drive with realistic
GPS breadcrumbs generated from a simple bearing walk.
"""

import math
import random
from datetime import datetime, timedelta, timezone

from .fordapi import TirePressures, VehicleLocation, VehicleStatus
from . import database as db

# ---- Fake live status ----

_BASE_FUEL = 72.0        # %
_FUEL_DRIFT = 0.0        # changes slightly each poll to simulate consumption

def get_demo_status() -> VehicleStatus:
    global _FUEL_DRIFT
    _FUEL_DRIFT -= random.uniform(0, 0.05)   # very slow drain
    fuel = max(5.0, _BASE_FUEL + _FUEL_DRIFT)

    return VehicleStatus(
        vin="DEMO0000000000000",
        location=VehicleLocation(
            lat=30.2672 + random.uniform(-0.0001, 0.0001),
            lng=-97.7431 + random.uniform(-0.0001, 0.0001),
            gps_state="NOMINAL",
        ),
        speed=0.0,
        fuel_level_pct=round(fuel, 1),
        fuel_range_km=round(fuel / 100 * 580, 1),   # ~580 km full tank
        oil_life_pct=68.0,
        odometer=14_237.0,
        battery_voltage=12.6,
        tires=TirePressures(fl=35.0, fr=35.0, rl=34.0, rr=34.0),
        locked=True,
        alarm_set=True,
        raw={},
    )


# ---- Trip seeder ----

def _walk(start_lat, start_lng, steps, bearing_deg, step_m=80):
    """Generate a list of (lat, lng) points walking in a given bearing."""
    pts = [(start_lat, start_lng)]
    lat, lng = start_lat, start_lng
    R = 6_371_000
    for _ in range(steps):
        bearing = math.radians(bearing_deg + random.uniform(-12, 12))
        d = step_m * random.uniform(0.8, 1.2)
        lat2 = lat + (d / R) * math.cos(bearing) * (180 / math.pi)
        lng2 = lng + (d / R) * math.sin(bearing) / math.cos(math.radians(lat)) * (180 / math.pi)
        pts.append((lat2, lng2))
        lat, lng = lat2, lng2
    return pts


# Seed data: (start_lat, start_lng, steps, bearing, days_ago, hour)
_DEMO_TRIPS = [
    (30.2672, -97.7431,  55, 45,   1, 8),    # morning commute NE
    (30.2672, -97.7431,  55, 225, 1, 17),    # return SW
    (30.2672, -97.7431,  90, 10,   3, 9),    # longer drive north
    (30.3050, -97.7300,  90, 190, 3, 11),    # return south
    (30.2672, -97.7431,  40, 270, 5, 19),    # short errand west
    (30.2672, -97.7431,  30, 90,  7, 7),     # quick east
    (30.2672, -97.7431, 120, 135, 9, 10),    # longer SE trip
    (30.3400, -97.6800, 120, 315, 9, 13),    # return NW
]


def seed_demo_db() -> None:
    """Insert fake trips + points if the DB is empty."""
    existing = db.get_trips(limit=1)
    if existing:
        return   # already seeded

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for (slat, slng, steps, bearing, days_ago, hour) in _DEMO_TRIPS:
        pts = _walk(slat, slng, steps, bearing)
        trip_start = now - timedelta(days=days_ago, hours=24 - hour)
        trip_id = db.open_trip(trip_start, pts[0][0], pts[0][1])

        distance_km = 0.0
        prev = pts[0]
        for i, (lat, lng) in enumerate(pts):
            ts = trip_start + timedelta(seconds=i * 12)
            speed = random.uniform(30, 70)
            db.insert_location_point(trip_id, ts, lat, lng, speed)
            if i > 0:
                from .trips import haversine_km
                distance_km += haversine_km(prev[0], prev[1], lat, lng)
            prev = (lat, lng)

        trip_end = trip_start + timedelta(seconds=len(pts) * 12)
        db.close_trip(trip_id, trip_end, pts[-1][0], pts[-1][1], distance_km)

    # Seed snapshots — fuel history for the sparkline
    for i in range(30):
        ts = now - timedelta(days=30 - i)
        fuel = max(10.0, 95.0 - i * 1.8 + random.uniform(-2, 2))
        db.insert_snapshot(
            ts=ts,
            fuel_level=round(fuel, 1),
            fuel_range_km=round(fuel / 100 * 580, 1),
            odometer_km=14_237.0 - (30 - i) * 18,
            oil_life=70.0,
            battery_voltage=12.6,
            tires=(35.0, 35.0, 34.0, 34.0),
        )
