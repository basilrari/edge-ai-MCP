#!/usr/bin/env python3
"""
MAVSDK Drone MCP Server
========================
MCP (Model Context Protocol) server that exposes drone control via MAVSDK.
Communicates with PX4/ArduPilot flight controllers through MAVSDK.

Transport: stdio (for Hermes MCP integration)
Supports: UDP (default), Serial connections

Usage:
  python3 server.py                          # stdio mode (for MCP)
  python3 server.py --connect udp://:14550   # with custom connection
"""

import asyncio
import sys
import argparse
import json
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mavsdk import System
from mavsdk.offboard import OffboardError, VelocityBodyYawspeed, PositionNedYaw
from mavsdk.mavlink_direct import MavlinkMessage


# ─── MCP Server ───────────────────────────────────────────────────────────────

mcp = FastMCP(
    "drone-mavsdk",
    instructions="""Control a drone via MAVSDK through PX4/ArduPilot.

Connect first with `connect` tool (default UDP :14550).
Then arm, takeoff, fly, land, etc.

All position tools use GPS coordinates (lat/lon/alt AMSL).
Velocity tools use body-frame (forward/right/down).

For camera/gimbal: take control first with gimbal_take_control().
For landing gear: deployed by default on takeoff, retract in flight.
""",
)

drone: Optional[System] = None
connected = False
CONNECTION_STRING = "udp://:14550"  # Default


# ─── Helpers ───────────────────────────────────────────────────────────────────

async def _require_connection() -> str | None:
    """Return None if OK, or error string if not connected."""
    global drone
    if not drone or not connected:
        return "Not connected. Call connect() first."
    return None


async def _send_mavlink_command(command: int, param1: float = 0, param2: float = 0,
                                param3: float = 0, param4: float = 0,
                                param5: float = 0, param6: float = 0,
                                param7: float = 0) -> None:
    """Send a raw MAVLink COMMAND_LONG via mavlink_direct."""
    msg = MavlinkMessage(
        message_name="COMMAND_LONG",
        system_id=255,
        component_id=0,
        target_system_id=1,
        target_component_id=1,
        fields_json=json.dumps({
            "command": command,
            "confirmation": 0,
            "param1": param1,
            "param2": param2,
            "param3": param3,
            "param4": param4,
            "param5": param5,
            "param6": param6,
            "param7": param7,
        }),
    )
    await drone.mavlink_direct.send_message(msg)


# ─── Connection Management ────────────────────────────────────────────────────

@mcp.tool()
async def connect(connection_string: str = "udp://:14550") -> str:
    """Connect to the drone's flight controller.

    Args:
        connection_string: Connection endpoint.
           UDP:  "udp://:14550" (listen) or "udp://192.168.1.10:14550" (target)
           Serial: "serial:///dev/ttyUSB0:57600"
    """
    global drone, connected, CONNECTION_STRING

    if connected and drone:
        return f"Already connected. Call disconnect() first to reconnect."

    CONNECTION_STRING = connection_string
    drone = System()
    await drone.connect(system_address=connection_string)

    print(f"Connecting to {connection_string}...", file=sys.stderr)

    # Wait for connection with timeout
    try:
        async with asyncio.timeout(15):
            await drone.telemetry.health()
    except asyncio.TimeoutError:
        drone = None
        connected = False
        raise TimeoutError(
            f"Connection timeout after 15s. Is the flight controller reachable at '{connection_string}'?"
        )

    connected = True
    return f"Connected to drone at {connection_string}"


@mcp.tool()
async def disconnect() -> str:
    """Disconnect from the drone. Call connect() to reconnect."""
    global drone, connected
    drone = None
    connected = False
    return "Disconnected."


@mcp.tool()
async def is_connected() -> bool:
    """Check if drone is connected and healthy."""
    global drone, connected
    if not connected or not drone:
        return False
    try:
        health = await drone.telemetry.health()
        return health.is_global_position_ok and health.is_armable
    except Exception:
        return False


# ─── Arming / Disarming ──────────────────────────────────────────────────────

@mcp.tool()
async def arm() -> str:
    """Arm the drone motors. Motors will spin but drone stays on ground."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.arm()
        return "Armed."
    except Exception as e:
        return f"Failed to arm: {e}"


@mcp.tool()
async def disarm() -> str:
    """Disarm the drone motors."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.disarm()
        return "Disarmed."
    except Exception as e:
        return f"Failed to disarm: {e}"


@mcp.tool()
async def is_armed() -> bool:
    """Check if the drone is currently armed."""
    err = await _require_connection()
    if err: return False
    return await drone.telemetry.armed()


# ─── Flight Actions ──────────────────────────────────────────────────────────

@mcp.tool()
async def takeoff(altitude_m: float = 10.0) -> str:
    """Take off to a specified altitude above home.

    Args:
        altitude_m: Target altitude in meters above takeoff position.
    """
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.takeoff()
        await asyncio.sleep(2)
        # Wait until we reach target altitude
        async for position in drone.telemetry.position():
            if abs(position.relative_altitude_m - altitude_m) < 1.0:
                break
        return f"Takeoff complete at {altitude_m}m."
    except Exception as e:
        return f"Takeoff failed: {e}"


@mcp.tool()
async def land() -> str:
    """Land at the current position."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.land()
        return "Landing..."
    except Exception as e:
        return f"Land failed: {e}"


@mcp.tool()
async def return_to_launch() -> str:
    """Return to launch position and land."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.return_to_launch()
        return "Returning to launch..."
    except Exception as e:
        return f"RTL failed: {e}"


@mcp.tool()
async def hold() -> str:
    """Hold position (loiter). Stays in current location."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.hold()
        return "Holding position."
    except Exception as e:
        return f"Hold failed: {e}"


@mcp.tool()
async def emergency_stop() -> str:
    """Kill motors immediately. Drone will drop. Use only in emergencies!"""
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.kill()
        return "KILL command sent. Motors stopped."
    except Exception as e:
        return f"Kill failed: {e}"


# ─── Navigation ──────────────────────────────────────────────────────────────

@mcp.tool()
async def goto_location(lat: float, lon: float, alt_m: float) -> str:
    """Fly to a GPS position at specified altitude.

    Args:
        lat: Target latitude in degrees.
        lon: Target longitude in degrees.
        alt_m: Target altitude AMSL (above mean sea level) in meters.
    """
    err = await _require_connection()
    if err: return err

    try:
        await drone.action.goto_location(lat, lon, alt_m, 0)
        return f"Navigating to ({lat:.6f}, {lon:.6f}) at {alt_m}m AMSL."
    except Exception as e:
        return f"Goto failed: {e}"


@mcp.tool()
async def set_velocity(forward_ms: float, right_ms: float, down_ms: float, yaw_deg_s: float = 0.0) -> str:
    """Set body-frame velocity. Drone must be in offboard mode.

    Args:
        forward_ms: Forward velocity (m/s, positive = forward)
        right_ms: Right velocity (m/s, positive = right)
        down_ms: Down velocity (m/s, positive = down)
        yaw_deg_s: Yaw rate (deg/s, positive = clockwise)
    """
    err = await _require_connection()
    if err: return err

    try:
        await drone.offboard.set_velocity_body(
            VelocityBodyYawspeed(forward_ms, right_ms, down_ms, yaw_deg_s)
        )
        return f"Velocity set: fwd={forward_ms}, right={right_ms}, down={down_ms}, yaw={yaw_deg_s} deg/s."
    except OffboardError as e:
        return f"Offboard error: {e}. Ensure offboard mode is active."
    except Exception as e:
        return f"Velocity set failed: {e}"


@mcp.tool()
async def start_offboard() -> str:
    """Start offboard mode. Required before set_velocity()."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.offboard.start()
        return "Offboard mode started."
    except OffboardError as e:
        return f"Failed to start offboard: {e}"


@mcp.tool()
async def stop_offboard() -> str:
    """Stop offboard mode. Returns control to RC or auto mode."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.offboard.stop()
        return "Offboard mode stopped."
    except Exception as e:
        return f"Failed to stop offboard: {e}"


# ─── Telemetry ───────────────────────────────────────────────────────────────

@mcp.tool()
async def get_telemetry() -> str:
    """Get current drone telemetry: position, attitude, battery, flight mode."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        pos = await drone.telemetry.position()
        att = await drone.telemetry.attitude_euler()
        bat = await drone.telemetry.battery()
        flight_mode = await drone.telemetry.flight_mode()
        armed = await drone.telemetry.armed()
        health = await drone.telemetry.health()

        return json.dumps({
            "position": {
                "lat": pos.latitude_deg,
                "lon": pos.longitude_deg,
                "alt_amsl_m": pos.absolute_altitude_m,
                "alt_relative_m": pos.relative_altitude_m,
            },
            "attitude": {
                "roll_deg": att.roll_deg,
                "pitch_deg": att.pitch_deg,
                "yaw_deg": att.yaw_deg,
            },
            "battery": {
                "voltage_v": bat.voltage_v,
                "remaining_pct": bat.remaining_percent * 100,
            },
            "flight_mode": str(flight_mode),
            "armed": armed,
            "health": {
                "global_position_ok": health.is_global_position_ok,
                "armable": health.is_armable,
                "home_position_ok": health.is_home_position_ok,
                "local_position_ok": health.is_local_position_ok,
            },
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_battery() -> str:
    """Get battery voltage and remaining percentage."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        bat = await drone.telemetry.battery()
        return json.dumps({
            "voltage_v": bat.voltage_v,
            "remaining_pct": round(bat.remaining_percent * 100, 1),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_flight_mode() -> str:
    """Get current flight mode (e.g. 'HOLD', 'OFFBOARD', 'AUTO', etc.)."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        mode = await drone.telemetry.flight_mode()
        return str(mode)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def set_flight_mode(mode: str = "HOLD") -> str:
    """Set flight mode. Common modes: HOLD, OFFBOARD, AUTO, RTL, LAND, MISSION.

    Args:
        mode: Flight mode name. Case-insensitive.
    """
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    mode_upper = mode.upper()
    mode_map = {
        "HOLD": "hold",
        "RTL": "return_to_launch",
        "LAND": "land",
        "AUTO": "mission",
        "MISSION": "mission",
        "OFFBOARD": "offboard",
    }

    if mode_upper not in mode_map:
        modes = ", ".join(mode_map.keys())
        return f"Unknown mode '{mode}'. Available: {modes}"

    try:
        action_map = {
            "hold": drone.action.hold,
            "return_to_launch": drone.action.return_to_launch,
            "land": drone.action.land,
            "mission": drone.action.set_mission,
        }
        action = action_map.get(mode_map[mode_upper])
        if action:
            await action()
            return f"Flight mode set to {mode_upper}."
        return f"Cannot set {mode_upper} from here."
    except Exception as e:
        return f"Set mode failed: {e}"


# ─── Mission Management ─────────────────────────────────────────────────────

@mcp.tool()
async def upload_mission(waypoints_json: str) -> str:
    """Upload a mission plan. Waypoints as JSON array.

    Args:
        waypoints_json: JSON array of waypoints, each with lat, lon, alt_m.
           Example: [{"lat": 47.398, "lon": 8.545, "alt_m": 30}]
    """
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        import mavsdk.mission_raw as mission_raw

        waypoints = json.loads(waypoints_json)
        if not isinstance(waypoints, list):
            return json.dumps({"error": "waypoints_json must be a JSON array"})

        mission_items = []
        for i, wp in enumerate(waypoints):
            lat = int(wp["lat"] * 1e7)  # MAVLink uses degE7
            lon = int(wp["lon"] * 1e7)
            alt = wp["alt_m"]
            mission_items.append(
                mission_raw.MissionItem(
                    lat,
                    lon,
                    alt,
                    5.0,  # speed m/s
                    True,  # fly_through
                    float("nan"),  # gimbal pitch
                    float("nan"),  # gimbal yaw
                    mission_raw.MissionItemMissionType.MISSION,
                )
            )

        await drone.mission_raw.upload_mission(mission_items)
        return f"Mission uploaded: {len(mission_items)} waypoints."
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def start_mission() -> str:
    """Start executing the uploaded mission plan."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        await drone.mission_raw.start_mission()
        return "Mission started."
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def pause_mission() -> str:
    """Pause the currently executing mission."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        await drone.mission_raw.pause_mission()
        return "Mission paused."
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Gimbal Control ─────────────────────────────────────────────────────────

@mcp.tool()
async def gimbal_set_angles(pitch_deg: float = 0.0, yaw_deg: float = 0.0, roll_deg: float = 0.0) -> str:
    """Set gimbal orientation in degrees.

    Args:
        pitch_deg: Gimbal pitch (tilt) in degrees. Negative = look down.
        yaw_deg: Gimbal yaw (pan) in degrees relative to vehicle heading.
        roll_deg: Gimbal roll in degrees.
    """
    err = await _require_connection()
    if err: return err

    try:
        await drone.gimbal.set_angles(pitch_deg, yaw_deg, roll_deg)
        return f"Gimbal set to pitch={pitch_deg}°, yaw={yaw_deg}°, roll={roll_deg}°."
    except Exception as e:
        return f"Gimbal set_angles failed: {e}"


@mcp.tool()
async def gimbal_take_control() -> str:
    """Take control of the gimbal. Required before setting angles."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.gimbal.take_control()
        return "Gimbal control acquired."
    except Exception as e:
        return f"Gimbal take_control failed: {e}"


@mcp.tool()
async def gimbal_release_control() -> str:
    """Release gimbal control back to RC or auto mode."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.gimbal.release_control()
        return "Gimbal control released."
    except Exception as e:
        return f"Gimbal release_control failed: {e}"


@mcp.tool()
async def gimbal_point_at_location(lat: float, lon: float, alt_m: float) -> str:
    """Point the gimbal at a specific GPS location (ROI mode).

    Args:
        lat: Target latitude in degrees.
        lon: Target longitude in degrees.
        alt_m: Target altitude AMSL in meters.
    """
    err = await _require_connection()
    if err: return err

    try:
        await drone.gimbal.set_roi_location(lat, lon, alt_m)
        return f"Gimbal pointing at ({lat:.6f}, {lon:.6f}) at {alt_m}m."
    except Exception as e:
        return f"Gimbal ROI failed: {e}"


@mcp.tool()
async def gimbal_get_attitude() -> str:
    """Get current gimbal orientation angles."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        att = await drone.gimbal.get_attitude()
        return json.dumps({
            "pitch_deg": att.pitch_deg,
            "yaw_deg": att.yaw_deg,
            "roll_deg": att.roll_deg,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Camera Control ──────────────────────────────────────────────────────────

@mcp.tool()
async def camera_take_photo() -> str:
    """Trigger the camera shutter to take a single photo."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.camera.take_photo()
        return "Photo taken."
    except Exception as e:
        return f"Take photo failed: {e}"


@mcp.tool()
async def camera_start_recording() -> str:
    """Start video recording."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.camera.start_video()
        return "Video recording started."
    except Exception as e:
        return f"Start recording failed: {e}"


@mcp.tool()
async def camera_stop_recording() -> str:
    """Stop video recording."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.camera.stop_video()
        return "Video recording stopped."
    except Exception as e:
        return f"Stop recording failed: {e}"


@mcp.tool()
async def camera_set_mode(mode: str = "photo") -> str:
    """Set camera mode.

    Args:
        mode: 'photo' or 'video'
    """
    err = await _require_connection()
    if err: return err

    try:
        from mavsdk.camera import Mode
        mode_map = {"photo": Mode.PHOTO, "video": Mode.VIDEO}
        if mode.lower() not in mode_map:
            return f"Unknown mode '{mode}'. Use 'photo' or 'video'."
        await drone.camera.set_mode(mode_map[mode.lower()])
        return f"Camera mode set to {mode}."
    except Exception as e:
        return f"Set camera mode failed: {e}"


@mcp.tool()
async def camera_get_mode() -> str:
    """Get current camera mode (photo or video)."""
    err = await _require_connection()
    if err: return err

    try:
        from mavsdk.camera import Mode
        mode = await drone.camera.get_mode()
        return "photo" if mode == Mode.PHOTO else "video"
    except Exception as e:
        return f"Get camera mode failed: {e}"


@mcp.tool()
async def camera_zoom_in() -> str:
    """Start zooming in."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.camera.zoom_in_start()
        return "Zooming in..."
    except Exception as e:
        return f"Zoom in failed: {e}"


@mcp.tool()
async def camera_zoom_out() -> str:
    """Start zooming out."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.camera.zoom_out_start()
        return "Zooming out..."
    except Exception as e:
        return f"Zoom out failed: {e}"


@mcp.tool()
async def camera_zoom_stop() -> str:
    """Stop zooming."""
    err = await _require_connection()
    if err: return err

    try:
        await drone.camera.zoom_stop()
        return "Zoom stopped."
    except Exception as e:
        return f"Zoom stop failed: {e}"


@mcp.tool()
async def camera_get_storage() -> str:
    """Get camera storage status (used/total space)."""
    err = await _require_connection()
    if err: return json.dumps({"error": err})

    try:
        storage = await drone.camera.get_storage()
        return json.dumps({
            "total_bytes": storage.total_bytes,
            "used_bytes": storage.used_bytes,
            "free_bytes": storage.available_bytes,
            "used_pct": round(storage.used_bytes / storage.total_bytes * 100, 1) if storage.total_bytes > 0 else 0,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Landing Gear ────────────────────────────────────────────────────────────
# MAV_CMD_LANDING_GEAR = 210 (0xD2)
# param1: 1 = deploy (extend/down), 0 = retract (up)

@mcp.tool()
async def landing_gear_deploy() -> str:
    """Deploy (extend) landing gear down."""
    err = await _require_connection()
    if err: return err

    try:
        await _send_mavlink_command(command=210, param1=1.0)
        return "Landing gear deploying (extending down)."
    except Exception as e:
        return f"Landing gear deploy failed: {e}"


@mcp.tool()
async def landing_gear_retract() -> str:
    """Retract landing gear up (in-flight only)."""
    err = await _require_connection()
    if err: return err

    try:
        await _send_mavlink_command(command=210, param1=0.0)
        return "Landing gear retracting (going up)."
    except Exception as e:
        return f"Landing gear retract failed: {e}"


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MAVSDK Drone MCP Server")
    parser.add_argument(
        "--connect",
        default=None,
        help="Connection string (e.g. 'udp://:14550', 'serial:///dev/ttyUSB0:57600')",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport (stdio for Hermes, sse for HTTP)",
    )
    args = parser.parse_args()

    if args.connect:
        global CONNECTION_STRING
        CONNECTION_STRING = args.connect

    print(f"MAVSDK MCP Server starting...", file=sys.stderr)
    print(f"Transport: {args.transport}", file=sys.stderr)
    print(f"Default connection: {CONNECTION_STRING}", file=sys.stderr)
    if args.connect:
        print(f"Overridden connection: {args.connect}", file=sys.stderr)

    # Run the MCP server
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
