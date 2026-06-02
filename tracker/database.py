import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Optional

from . import config


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trips (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time  TIMESTAMP NOT NULL,
                end_time    TIMESTAMP,
                start_lat   REAL NOT NULL,
                start_lng   REAL NOT NULL,
                end_lat     REAL,
                end_lng     REAL,
                distance_km REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS location_points (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id  INTEGER REFERENCES trips(id) ON DELETE CASCADE,
                ts       TIMESTAMP NOT NULL,
                lat      REAL NOT NULL,
                lng      REAL NOT NULL,
                speed    REAL
            );

            CREATE INDEX IF NOT EXISTS idx_location_trip ON location_points(trip_id);
            CREATE INDEX IF NOT EXISTS idx_location_ts   ON location_points(ts);

            CREATE TABLE IF NOT EXISTS vehicle_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              TIMESTAMP NOT NULL,
                fuel_level      REAL,
                fuel_range_km   REAL,
                odometer_km     REAL,
                oil_life        REAL,
                battery_voltage REAL,
                tire_fl         REAL,
                tire_fr         REAL,
                tire_rl         REAL,
                tire_rr         REAL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshot_ts ON vehicle_snapshots(ts);
        """)


# --- Dataclasses returned by query helpers ---

@dataclass
class Trip:
    id: int
    start_time: datetime
    end_time: Optional[datetime]
    start_lat: float
    start_lng: float
    end_lat: Optional[float]
    end_lng: Optional[float]
    distance_km: float


@dataclass
class LocationPoint:
    id: int
    trip_id: Optional[int]
    ts: datetime
    lat: float
    lng: float
    speed: Optional[float]


@dataclass
class VehicleSnapshot:
    id: int
    ts: datetime
    fuel_level: Optional[float]
    fuel_range_km: Optional[float]
    odometer_km: Optional[float]
    oil_life: Optional[float]
    battery_voltage: Optional[float]
    tire_fl: Optional[float]
    tire_fr: Optional[float]
    tire_rl: Optional[float]
    tire_rr: Optional[float]


# --- Write helpers ---

def insert_snapshot(
    ts: datetime,
    fuel_level: Optional[float],
    fuel_range_km: Optional[float],
    odometer_km: Optional[float],
    oil_life: Optional[float],
    battery_voltage: Optional[float],
    tires: tuple[Optional[float], Optional[float], Optional[float], Optional[float]],
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO vehicle_snapshots
               (ts, fuel_level, fuel_range_km, odometer_km, oil_life, battery_voltage,
                tire_fl, tire_fr, tire_rl, tire_rr)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ts, fuel_level, fuel_range_km, odometer_km, oil_life, battery_voltage, *tires),
        )
        return cur.lastrowid


def open_trip(ts: datetime, lat: float, lng: float) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO trips (start_time, start_lat, start_lng) VALUES (?,?,?)",
            (ts, lat, lng),
        )
        return cur.lastrowid


def close_trip(trip_id: int, ts: datetime, lat: float, lng: float, distance_km: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE trips SET end_time=?, end_lat=?, end_lng=?, distance_km=? WHERE id=?",
            (ts, lat, lng, distance_km, trip_id),
        )


def insert_location_point(
    trip_id: Optional[int], ts: datetime, lat: float, lng: float, speed: Optional[float]
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO location_points (trip_id, ts, lat, lng, speed) VALUES (?,?,?,?,?)",
            (trip_id, ts, lat, lng, speed),
        )
        return cur.lastrowid


def update_trip_distance(trip_id: int, distance_km: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE trips SET distance_km=? WHERE id=?",
            (distance_km, trip_id),
        )


# --- Read helpers ---

def _row_to_trip(row: sqlite3.Row) -> Trip:
    return Trip(
        id=row["id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        start_lat=row["start_lat"],
        start_lng=row["start_lng"],
        end_lat=row["end_lat"],
        end_lng=row["end_lng"],
        distance_km=row["distance_km"],
    )


def _row_to_point(row: sqlite3.Row) -> LocationPoint:
    return LocationPoint(
        id=row["id"],
        trip_id=row["trip_id"],
        ts=row["ts"],
        lat=row["lat"],
        lng=row["lng"],
        speed=row["speed"],
    )


def _row_to_snapshot(row: sqlite3.Row) -> VehicleSnapshot:
    return VehicleSnapshot(
        id=row["id"],
        ts=row["ts"],
        fuel_level=row["fuel_level"],
        fuel_range_km=row["fuel_range_km"],
        odometer_km=row["odometer_km"],
        oil_life=row["oil_life"],
        battery_voltage=row["battery_voltage"],
        tire_fl=row["tire_fl"],
        tire_fr=row["tire_fr"],
        tire_rl=row["tire_rl"],
        tire_rr=row["tire_rr"],
    )


def get_trips(limit: int = 50, offset: int = 0) -> list[Trip]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trips ORDER BY start_time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_trip(r) for r in rows]


def get_trip(trip_id: int) -> Optional[Trip]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
    return _row_to_trip(row) if row else None


def get_trip_points(trip_id: int) -> list[LocationPoint]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM location_points WHERE trip_id=? ORDER BY ts ASC",
            (trip_id,),
        ).fetchall()
    return [_row_to_point(r) for r in rows]


def get_latest_snapshot() -> Optional[VehicleSnapshot]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM vehicle_snapshots ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    return _row_to_snapshot(row) if row else None


def get_latest_location() -> Optional[LocationPoint]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM location_points ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    return _row_to_point(row) if row else None


def get_open_trip() -> Optional[Trip]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trips WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
    return _row_to_trip(row) if row else None


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(distance_km),0) as dist FROM trips WHERE end_time IS NOT NULL"
        ).fetchone()
        week = conn.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(distance_km),0) as dist
               FROM trips
               WHERE end_time IS NOT NULL
               AND start_time >= datetime('now', '-7 days')"""
        ).fetchone()
        month = conn.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(distance_km),0) as dist
               FROM trips
               WHERE end_time IS NOT NULL
               AND start_time >= datetime('now', '-30 days')"""
        ).fetchone()
    return {
        "total_trips": total["cnt"],
        "total_distance_km": round(total["dist"], 2),
        "week_trips": week["cnt"],
        "week_distance_km": round(week["dist"], 2),
        "month_trips": month["cnt"],
        "month_distance_km": round(month["dist"], 2),
    }


def get_fuel_history(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ts, fuel_level, fuel_range_km
               FROM vehicle_snapshots
               WHERE fuel_level IS NOT NULL
               ORDER BY ts DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [{"ts": r["ts"], "fuel_level": r["fuel_level"], "fuel_range_km": r["fuel_range_km"]} for r in rows]
