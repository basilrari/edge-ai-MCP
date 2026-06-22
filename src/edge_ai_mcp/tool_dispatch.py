"""Map SAR gateway LLM tool names to MAVSDK calls (drone-http compatible)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from . import limits, mission_builder, mavsdk_client
from .telemetry_cache import get_cache

# Same names the gateway LLM may emit (see gateway/src/llm.rs).
GATEWAY_TOOL_NAMES: tuple[str, ...] = (
    "arm",
    "disarm",
    "force_arm",
    "set_mode_auto",
    "set_mode_guided",
    "takeoff",
    "start_mission",
    "mission_set_current",
    "goto_location",
    "move_forward",
    "hover",
    "return_to_home",
    "land_immediately",
    "circle_search",
    "retry_streams",
    "mission_interrupt",
    "mission_resume",
    "waypoint_inject",
)


def _params_obj(params: Any) -> dict[str, Any]:
    if isinstance(params, dict):
        return params
    return {}


async def _alt_amsl_for_rel_home(alt_rel_m: float) -> float:
    cache = get_cache()
    if cache.home_alt_m is not None:
        return cache.home_alt_m + alt_rel_m
    if cache.alt_amsl_m is not None and cache.alt_rel_m is not None:
        return cache.alt_amsl_m - cache.alt_rel_m + alt_rel_m
    return alt_rel_m


async def apply_gateway_tool(tool: str, params: Any = None) -> None:
    """Run one gateway tool via MAVSDK. Raises RuntimeError on failure."""
    if not mavsdk_client.is_connected():
        raise RuntimeError("mavlink_not_connected")

    p = _params_obj(params)
    drone = mavsdk_client.get_drone()
    action = drone.action
    mission = drone.mission_raw

    if tool == "arm" or tool == "force_arm":
        await action.arm()
        return

    if tool == "disarm":
        await action.disarm()
        return

    if tool in ("set_mode_guided", "hover"):
        await action.hold()
        return

    if tool == "takeoff":
        alt_m = p.get("altitude_m")
        if alt_m is None:
            cache = get_cache()
            if cache.alt_rel_m is not None and cache.alt_rel_m > 1:
                alt_m = cache.alt_rel_m
            else:
                alt_m = 15.0
        alt_f = float(alt_m)
        if msg := limits.check_altitude_m(alt_f):
            raise RuntimeError(msg)
        await action.set_takeoff_altitude(alt_f)
        await action.takeoff()
        return

    if tool == "start_mission" or tool == "set_mode_auto":
        await mission.start_mission()
        return

    if tool == "mission_set_current":
        seq = p.get("seq")
        if seq is None:
            raise RuntimeError("mission_set_current requires params.seq")
        await mission.set_current_mission_item(int(seq))
        return

    if tool == "goto_location":
        lat = float(p["lat_deg"])
        lon = float(p["lon_deg"])
        alt_rel = float(p.get("alt_m", 15))
        if msg := limits.check_lat_lon(lat, lon):
            raise RuntimeError(msg)
        if msg := limits.check_altitude_m(alt_rel):
            raise RuntimeError(msg)
        origin = await mavsdk_client.origin_for_limits()
        if origin is None:
            raise RuntimeError("Need home or position for distance check")
        if msg := limits.check_distance_from(
            limits.Position(*origin), limits.Position(lat, lon)
        ):
            raise RuntimeError(msg)
        alt_amsl = await _alt_amsl_for_rel_home(alt_rel)
        await action.goto_location(lat, lon, alt_amsl, 0.0)
        return

    if tool == "waypoint_inject":
        if "waypoint_text" in p:
            raise RuntimeError("waypoint_text not supported via MAVSDK; use lat_deg/lon_deg/alt_m")
        lat = float(p["lat_deg"])
        lon = float(p["lon_deg"])
        alt_rel = float(p.get("alt_m", 15))
        await apply_gateway_tool(
            "goto_location", {"lat_deg": lat, "lon_deg": lon, "alt_m": alt_rel}
        )
        return

    if tool == "return_to_home":
        await action.return_to_launch()
        return

    if tool == "land_immediately":
        await action.land()
        return

    if tool == "mission_interrupt":
        await mission.pause_mission()
        await action.hold()
        return

    if tool == "mission_resume":
        await mission.start_mission()
        return

    if tool == "move_forward":
        speed = float(p.get("speed_m_s", 3))
        if msg := limits.check_speed_m_s(speed):
            raise RuntimeError(msg)
        from mavsdk.offboard import VelocityBodyYawspeed

        try:
            await drone.offboard.set_velocity_body(
                VelocityBodyYawspeed(speed, 0.0, 0.0, 0.0)
            )
            await drone.offboard.start()
        except Exception as e:
            raise RuntimeError(f"move_forward/offboard failed: {e}") from e
        return

    if tool == "circle_search":
        raise RuntimeError("circle_search not available via MAVSDK (use mission or goto)")

    if tool == "retry_streams":
        await asyncio.sleep(0.05)
        return

    raise RuntimeError(f"unknown_drone_tool:{tool}")


async def upload_planner_mission(body: dict[str, Any]) -> int:
    """Mission planner upload (dashboard) via MissionRaw."""
    waypoints = body.get("waypoints") or []
    mission_json = json.dumps(
        {
            "include_takeoff": body.get("include_takeoff", True),
            "takeoff_alt_m": body.get("takeoff_alt_m", 15),
            "include_rtl": body.get("include_rtl", True),
            "waypoints": [
                {"lat": w["lat_deg"], "lon": w["lon_deg"], "alt_m": w["alt_m"]}
                for w in waypoints
            ],
        }
    )
    home = await mavsdk_client.home_position()
    parsed = mission_builder.parse_mission_json(
        mission_json,
        home_lat=home[0] if home else None,
        home_lon=home[1] if home else None,
    )
    origin = await mavsdk_client.origin_for_limits()
    if origin is None:
        raise RuntimeError("Need home or position for distance check")
    if msg := mission_builder.validate_mission_distances(
        limits.Position(*origin), parsed
    ):
        raise RuntimeError(msg)
    items = mission_builder.build_mission_items(parsed)
    await mavsdk_client.get_drone().mission_raw.upload_mission(items)
    return len(items)
