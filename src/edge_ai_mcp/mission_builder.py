"""Build ArduPilot mission items for MAVSDK MissionRaw (no raw MAVLink)."""

from __future__ import annotations

import json

import mavsdk.mission_raw as mission_raw

from . import config
from . import limits

MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_NAV_TAKEOFF = 22
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MISSION_TYPE_MISSION = 0


def _item(
    seq: int,
    command: int,
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
) -> mission_raw.MissionItem:
    return mission_raw.MissionItem(
        seq,
        MAV_FRAME_GLOBAL_RELATIVE_ALT,
        command,
        0,
        1,
        0.0,
        0.0,
        0.0,
        0.0,
        int(round(lat_deg * 1e7)),
        int(round(lon_deg * 1e7)),
        float(alt_m),
        MISSION_TYPE_MISSION,
    )


def parse_mission_json(
    raw: str,
    *,
    home_lat: float | None = None,
    home_lon: float | None = None,
) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("mission JSON must be an object")

    wps_raw = data.get("waypoints", [])
    if not isinstance(wps_raw, list):
        raise ValueError("waypoints must be an array")

    if msg := limits.check_waypoint_count(len(wps_raw)):
        raise ValueError(msg)

    waypoints: list[tuple[float, float, float]] = []
    for i, wp in enumerate(wps_raw):
        if not isinstance(wp, dict):
            raise ValueError(f"waypoint {i} must be an object")
        lat = float(wp.get("lat", wp.get("lat_deg", float("nan"))))
        lon = float(wp.get("lon", wp.get("lon_deg", float("nan"))))
        alt_m = float(wp.get("alt_m", float("nan")))
        if msg := limits.check_lat_lon(lat, lon):
            raise ValueError(f"waypoint {i}: {msg}")
        if msg := limits.check_altitude_m(alt_m):
            raise ValueError(f"waypoint {i}: {msg}")
        waypoints.append((lat, lon, alt_m))

    include_takeoff = bool(data.get("include_takeoff", True))
    takeoff_alt_m = float(data.get("takeoff_alt_m", config.DEFAULT_TAKEOFF_ALT_M))
    include_rtl = bool(data.get("include_rtl", True))

    if include_takeoff and (msg := limits.check_altitude_m(takeoff_alt_m)):
        raise ValueError(msg)

    hl = data.get("home_lat", home_lat)
    hn = data.get("home_lon", home_lon)
    if hl is not None:
        hl = float(hl)
    if hn is not None:
        hn = float(hn)

    return {
        "include_takeoff": include_takeoff,
        "takeoff_alt_m": takeoff_alt_m,
        "include_rtl": include_rtl,
        "waypoints": waypoints,
        "home_lat": hl,
        "home_lon": hn,
    }


def build_mission_items(parsed: dict) -> list[mission_raw.MissionItem]:
    items: list[mission_raw.MissionItem] = []
    seq = 0

    home_lat = parsed.get("home_lat")
    home_lon = parsed.get("home_lon")
    if home_lat is not None and home_lon is not None:
        items.append(_item(seq, MAV_CMD_NAV_WAYPOINT, home_lat, home_lon, 0.0))
        seq += 1
    elif parsed["waypoints"]:
        lat, lon, _ = parsed["waypoints"][0]
        items.append(_item(seq, MAV_CMD_NAV_WAYPOINT, lat, lon, 0.0))
        seq += 1

    if parsed["include_takeoff"]:
        items.append(_item(seq, MAV_CMD_NAV_TAKEOFF, 0.0, 0.0, parsed["takeoff_alt_m"]))
        seq += 1

    for lat, lon, alt_m in parsed["waypoints"]:
        items.append(_item(seq, MAV_CMD_NAV_WAYPOINT, lat, lon, alt_m))
        seq += 1

    if parsed["include_rtl"]:
        items.append(_item(seq, MAV_CMD_NAV_RETURN_TO_LAUNCH, 0.0, 0.0, 0.0))

    return items


def validate_mission_distances(origin: limits.Position, parsed: dict) -> str | None:
    for i, (lat, lon, _) in enumerate(parsed["waypoints"]):
        if msg := limits.check_distance_from(origin, limits.Position(lat, lon)):
            return f"waypoint {i}: {msg}"
    return None
