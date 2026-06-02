import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, database as db
from . import daemon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if config.DEMO_MODE:
        from .demo import seed_demo_db
        seed_demo_db()
        logger.info("DEMO MODE — using fake vehicle data")
    task = asyncio.create_task(daemon.run_daemon())
    logger.info("FordTracker server ready at http://localhost:8421")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="FordTracker", lifespan=lifespan)


# --- Helper to serialize datetimes ---
def _serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serialisable: {type(obj)}")


def _json(data) -> JSONResponse:
    import json
    return JSONResponse(content=json.loads(json.dumps(data, default=_serial)))


# =========================================================
#  API routes
# =========================================================

@app.get("/api/config")
async def api_config():
    return {"demo_mode": config.DEMO_MODE}


@app.get("/api/status")
async def api_status():
    """Latest vehicle snapshot from the DB + live data from daemon cache."""
    snap = db.get_latest_snapshot()
    loc = db.get_latest_location()
    live = daemon.get_last_status()
    trip_state = daemon.get_trip_state()

    result = {
        "snapshot": asdict(snap) if snap else None,
        "latest_location": asdict(loc) if loc else None,
        "active_trip_id": trip_state.active_trip_id,
        "trip_distance_km": round(trip_state.distance_km, 3) if trip_state.is_active() else None,
        # Pass through a few live fields that aren't stored in snapshots
        "locked": live.locked if live else None,
        "alarm_set": live.alarm_set if live else None,
    }
    return _json(result)


@app.get("/api/trips")
async def api_trips(limit: int = 50, offset: int = 0):
    trips = db.get_trips(limit=limit, offset=offset)
    return _json([asdict(t) for t in trips])


@app.get("/api/trips/{trip_id}")
async def api_trip_detail(trip_id: int):
    trip = db.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _json(asdict(trip))


@app.get("/api/trips/{trip_id}/points")
async def api_trip_points(trip_id: int):
    trip = db.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    points = db.get_trip_points(trip_id)
    return _json([asdict(p) for p in points])


@app.get("/api/stats")
async def api_stats():
    return _json(db.get_stats())


@app.get("/api/fuel-history")
async def api_fuel_history(limit: int = 100):
    return _json(db.get_fuel_history(limit=limit))


@app.post("/api/poll")
async def api_poll():
    """Manually trigger one poll cycle (useful for testing without waiting)."""
    status = await daemon.poll_once()
    if status is None:
        raise HTTPException(status_code=503, detail="Poll failed — check credentials and VIN")
    return _json({"ok": True, "location": asdict(status.location) if status.location else None})


# =========================================================
#  Static frontend
# =========================================================

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
