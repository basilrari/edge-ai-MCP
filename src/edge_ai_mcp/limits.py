"""Altitude, distance, and speed limits before MAVSDK calls."""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Position:
    lat: float
    lon: float


def haversine_m(a: Position, b: Position) -> float:
    r = 6_371_000.0
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dla = la2 - la1
    dlo = lo2 - lo1
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def check_altitude_m(alt_m: float) -> str | None:
    if not math.isfinite(alt_m):
        return "altitude must be a finite number"
    if alt_m < config.MIN_ALT_M or alt_m > config.MAX_ALT_M:
        return f"altitude {alt_m}m out of range ({config.MIN_ALT_M}–{config.MAX_ALT_M}m)"
    return None


def check_speed_m_s(speed_m_s: float) -> str | None:
    if not math.isfinite(speed_m_s):
        return "speed must be a finite number"
    if speed_m_s < 0 or speed_m_s > config.MAX_SPEED_M_S:
        return f"speed {speed_m_s}m/s out of range (0–{config.MAX_SPEED_M_S}m/s)"
    return None


def check_lat_lon(lat: float, lon: float) -> str | None:
    if not math.isfinite(lat) or not math.isfinite(lon):
        return "lat/lon must be finite"
    if abs(lat) > 90 or abs(lon) > 180:
        return "lat/lon out of range"
    if abs(lat) < 1e-6 and abs(lon) < 1e-6:
        return "lat/lon cannot be 0,0"
    return None


def check_distance_from(origin: Position, target: Position) -> str | None:
    d = haversine_m(origin, target)
    if d > config.MAX_DISTANCE_M:
        return f"target {d:.0f}m from origin exceeds max {config.MAX_DISTANCE_M}m"
    return None


def check_waypoint_count(count: int) -> str | None:
    if count < 1:
        return "at least one waypoint is required"
    if count > config.MAX_WAYPOINTS:
        return f"at most {config.MAX_WAYPOINTS} waypoints allowed"
    return None
