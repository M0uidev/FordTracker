"""
Background polling daemon.

Runs as an asyncio task inside the FastAPI lifespan. Every POLL_INTERVAL_SECONDS
it fetches vehicle status from the FordPass API, stores a snapshot, and runs
the trip state machine to detect / continue / close trips.
"""

import asyncio
import logging
from datetime import datetime, timezone

from . import config, database as db
from .fordapi import FordClient, VehicleStatus
from .trips import TripState

logger = logging.getLogger(__name__)

_state = TripState()
_client: FordClient | None = None
_last_status: VehicleStatus | None = None


def get_last_status() -> VehicleStatus | None:
    return _last_status


def get_trip_state() -> TripState:
    return _state


async def poll_once() -> VehicleStatus | None:
    """Fetch status, write snapshot, run trip logic. Returns the status or None on error."""
    global _last_status, _client

    if config.DEMO_MODE:
        from .demo import get_demo_status
        status = get_demo_status()
    else:
        if _client is None:
            try:
                _client = FordClient()
            except Exception as exc:
                logger.error("FordClient init failed: %s", exc)
                return None
        try:
            status = await asyncio.to_thread(_client.get_status)
        except Exception as exc:
            logger.error("FordPass API poll failed: %s", exc)
            return None

    _last_status = status
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # store as naive UTC

    # --- Always write a vehicle snapshot ---
    tires = (status.tires.fl, status.tires.fr, status.tires.rl, status.tires.rr)
    try:
        db.insert_snapshot(
            ts=now,
            fuel_level=status.fuel_level_pct,
            fuel_range_km=status.fuel_range_km,
            odometer_km=status.odometer,
            oil_life=status.oil_life_pct,
            battery_voltage=status.battery_voltage,
            tires=tires,
        )
    except Exception as exc:
        logger.error("Failed to write snapshot: %s", exc)

    # --- Trip logic requires a valid GPS fix ---
    if status.location is None:
        logger.debug("No GPS fix — skipping trip logic")
        return status

    lat, lng = status.location.lat, status.location.lng

    if _state.is_active():
        if _state.timed_out(now):
            # Close the current trip
            _close_trip(now, lat, lng)
        elif _state.has_moved(lat, lng):
            _continue_trip(now, lat, lng, status.speed)
        else:
            logger.debug("Vehicle stationary, trip #%d still open", _state.active_trip_id)
    else:
        if _state.has_moved(lat, lng):
            _start_trip(now, lat, lng, status.speed)
        else:
            logger.debug("No movement, no active trip")

    return status


def _start_trip(now: datetime, lat: float, lng: float, speed) -> None:
    try:
        trip_id = db.open_trip(now, lat, lng)
        db.insert_location_point(trip_id, now, lat, lng, speed)
    except Exception as exc:
        logger.error("Failed to open trip: %s", exc)
        return
    _state.active_trip_id = trip_id
    _state.distance_km = 0.0
    _state.last_lat = lat
    _state.last_lng = lng
    _state.last_point_time = now
    logger.info("Trip #%d started at (%.5f, %.5f)", trip_id, lat, lng)


def _continue_trip(now: datetime, lat: float, lng: float, speed) -> None:
    _state.advance(lat, lng)
    _state.last_point_time = now
    try:
        db.insert_location_point(_state.active_trip_id, now, lat, lng, speed)
        db.update_trip_distance(_state.active_trip_id, _state.distance_km)
    except Exception as exc:
        logger.error("Failed to record location point: %s", exc)
    logger.debug(
        "Trip #%d continuing at (%.5f, %.5f), %.2f km total",
        _state.active_trip_id, lat, lng, _state.distance_km,
    )


def _close_trip(now: datetime, lat: float, lng: float) -> None:
    trip_id = _state.active_trip_id
    try:
        db.close_trip(trip_id, now, lat, lng, _state.distance_km)
    except Exception as exc:
        logger.error("Failed to close trip #%d: %s", trip_id, exc)
    logger.info(
        "Trip #%d closed. Distance: %.2f km", trip_id, _state.distance_km
    )
    _state.reset()
    _state.last_lat = lat
    _state.last_lng = lng
    _state.last_point_time = now


async def run_daemon() -> None:
    """Main daemon loop — runs until cancelled."""
    logger.info(
        "FordTracker daemon started (poll every %ds)", config.POLL_INTERVAL_SECONDS
    )
    while True:
        await poll_once()
        await asyncio.sleep(config.POLL_INTERVAL_SECONDS)
