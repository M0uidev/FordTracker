"""
Thin wrapper around fordpass-python that normalises the raw vehiclestatus
JSON into typed dataclasses and handles token refresh transparently.

The vehiclestatus blob looks roughly like:
  {
    "GPS": {"latitude": "37.12", "longitude": "-122.34", "gpsState": "NOMINAL"},
    "fuel": {"fuelLevel": 0.87, "distanceToEmpty": 412.0},
    "oil":  {"oilLifeActual": 56.0},
    "odometer": {"value": 15000.0},
    "speed":    {"value": 65.0},
    "tirePressure": {
      "TIREFL": {"value": 35.0}, "TIREFR": {"value": 35.0},
      "TIRERL": {"value": 35.0}, "TIRERR": {"value": 35.0}
    },
    "battery": {"batteryStatusActual": {"value": 12.6}},
    "doorStatus": { ... },
    "lockStatus": {"value": "LOCKED"},
    "alarm":      {"value": "SET"}
  }
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fordpass import Vehicle as _FordVehicle

from . import config

logger = logging.getLogger(__name__)


@dataclass
class VehicleLocation:
    lat: float
    lng: float
    gps_state: str


@dataclass
class TirePressures:
    fl: Optional[float]
    fr: Optional[float]
    rl: Optional[float]
    rr: Optional[float]


@dataclass
class VehicleStatus:
    """Normalised snapshot of what the FordPass API returns."""
    vin: str
    # location
    location: Optional[VehicleLocation]
    speed: Optional[float]           # km/h or mph — raw from API
    # fuel
    fuel_level_pct: Optional[float]  # 0‥100
    fuel_range_km: Optional[float]
    # maintenance
    oil_life_pct: Optional[float]    # 0‥100
    odometer: Optional[float]        # raw unit from vehicle (usually miles for US)
    # electrical
    battery_voltage: Optional[float]
    # tyres
    tires: TirePressures
    # convenience booleans
    locked: Optional[bool]
    alarm_set: Optional[bool]
    # raw blob for anything we haven't mapped
    raw: dict


def _float(d: dict, *keys: str, default=None) -> Optional[float]:
    """Walk nested keys and return the first non-None float found."""
    for key in keys:
        d = d.get(key) if isinstance(d, dict) else None
        if d is None:
            return default
    try:
        return float(d) if d is not None else default
    except (TypeError, ValueError):
        return default


def _str(d: dict, *keys: str, default="") -> str:
    for key in keys:
        d = d.get(key) if isinstance(d, dict) else None
        if d is None:
            return default
    return str(d) if d is not None else default


class FordClient:
    def __init__(self) -> None:
        vin = config.FORDPASS_VIN
        if not vin:
            raise ValueError(
                "FORDPASS_VIN must be set in .env — check your vehicle registration "
                "card or FordPass app (Settings → Vehicle Details)."
            )
        self._vehicle = _FordVehicle(config.FORDPASS_EMAIL, config.FORDPASS_PASSWORD, vin)
        self._vin = vin

    def get_status(self) -> VehicleStatus:
        raw: dict = self._vehicle.status()

        # --- GPS ---
        gps = raw.get("GPS") or {}
        location: Optional[VehicleLocation] = None
        try:
            lat = float(gps["latitude"])
            lng = float(gps["longitude"])
            location = VehicleLocation(lat=lat, lng=lng, gps_state=gps.get("gpsState", ""))
        except (KeyError, TypeError, ValueError):
            pass

        # --- Speed ---
        speed = _float(raw.get("speed") or {}, "value")

        # --- Fuel ---
        fuel = raw.get("fuel") or {}
        fuel_level_raw = fuel.get("fuelLevel")
        fuel_level_pct: Optional[float] = None
        if fuel_level_raw is not None:
            try:
                v = float(fuel_level_raw)
                # API returns 0–1 range
                fuel_level_pct = round(v * 100, 1) if v <= 1.0 else round(v, 1)
            except (TypeError, ValueError):
                pass
        fuel_range = fuel.get("distanceToEmpty")
        fuel_range_km = float(fuel_range) if fuel_range is not None else None

        # --- Oil ---
        oil = raw.get("oil") or {}
        oil_life_pct = _float(oil, "oilLifeActual")

        # --- Odometer ---
        odometer = _float(raw.get("odometer") or {}, "value")

        # --- Battery ---
        battery_section = raw.get("battery") or {}
        battery_voltage = _float(battery_section.get("batteryStatusActual") or {}, "value")

        # --- Tires ---
        tp = raw.get("tirePressure") or {}
        tires = TirePressures(
            fl=_float(tp.get("TIREFL") or {}, "value"),
            fr=_float(tp.get("TIREFR") or {}, "value"),
            rl=_float(tp.get("TIRERL") or {}, "value"),
            rr=_float(tp.get("TIRERR") or {}, "value"),
        )

        # --- Lock / Alarm ---
        lock_val = _str(raw.get("lockStatus") or {}, "value")
        locked = lock_val.upper() == "LOCKED" if lock_val else None

        alarm_val = _str(raw.get("alarm") or {}, "value")
        alarm_set = alarm_val.upper() == "SET" if alarm_val else None

        return VehicleStatus(
            vin=self._vin,
            location=location,
            speed=speed,
            fuel_level_pct=fuel_level_pct,
            fuel_range_km=fuel_range_km,
            oil_life_pct=oil_life_pct,
            odometer=odometer,
            battery_voltage=battery_voltage,
            tires=tires,
            locked=locked,
            alarm_set=alarm_set,
            raw=raw,
        )
