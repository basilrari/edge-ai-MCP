"""Flight MCP tools (MAVSDK Action plugin)."""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from .. import limits, mavsdk_client, responses


def register_flight_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def arm() -> str:
        """Arm the drone motors."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().action.arm()
            return responses.ok({"armed": True})
        except Exception as e:
            return responses.err(f"Failed to arm: {e}")

    @mcp.tool()
    async def disarm() -> str:
        """Disarm the drone motors."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().action.disarm()
            return responses.ok({"armed": False})
        except Exception as e:
            return responses.err(f"Failed to disarm: {e}")

    @mcp.tool()
    async def is_armed() -> str:
        """Check if the drone is armed."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            armed = await mavsdk_client.get_drone().telemetry.armed().__anext__()
            return responses.ok({"armed": armed})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def takeoff(altitude_m: float = 15.0) -> str:
        """Take off to altitude above home (meters)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        if msg := limits.check_altitude_m(altitude_m):
            return responses.err(msg)
        try:
            drone = mavsdk_client.get_drone()
            await drone.action.set_takeoff_altitude(altitude_m)
            await drone.action.takeoff()
            return responses.ok({"takeoff_alt_m": altitude_m, "status": "takeoff_sent"})
        except Exception as e:
            return responses.err(f"Takeoff failed: {e}")

    @mcp.tool()
    async def land() -> str:
        """Land at the current position."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().action.land()
            return responses.ok({"status": "landing"})
        except Exception as e:
            return responses.err(f"Land failed: {e}")

    @mcp.tool()
    async def return_to_launch() -> str:
        """Return to launch position and land."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().action.return_to_launch()
            return responses.ok({"status": "rtl"})
        except Exception as e:
            return responses.err(f"RTL failed: {e}")

    @mcp.tool()
    async def hold() -> str:
        """Hold position (loiter)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().action.hold()
            return responses.ok({"status": "hold"})
        except Exception as e:
            return responses.err(f"Hold failed: {e}")

    @mcp.tool()
    async def goto_location(lat: float, lon: float, alt_m: float) -> str:
        """Fly to GPS position at altitude AMSL (meters)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        if msg := limits.check_lat_lon(lat, lon):
            return responses.err(msg)
        if msg := limits.check_altitude_m(alt_m):
            return responses.err(msg)
        origin = await mavsdk_client.origin_for_limits()
        if origin is None:
            return responses.err("Need home or current position for distance check")
        if msg := limits.check_distance_from(
            limits.Position(*origin), limits.Position(lat, lon)
        ):
            return responses.err(msg)
        try:
            await mavsdk_client.get_drone().action.goto_location(lat, lon, alt_m, 0.0)
            return responses.ok({"lat": lat, "lon": lon, "alt_amsl_m": alt_m})
        except Exception as e:
            return responses.err(f"Goto failed: {e}")

    @mcp.tool()
    async def emergency_stop() -> str:
        """Kill motors immediately. Use only in emergencies."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().action.kill()
            return responses.ok({"status": "kill_sent"})
        except Exception as e:
            return responses.err(f"Kill failed: {e}")

    @mcp.tool()
    async def pause_and_hold() -> str:
        """Pause mission and hold position (sub-mission interrupt)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            drone = mavsdk_client.get_drone()
            await drone.mission_raw.pause_mission()
            await drone.action.hold()
            return responses.ok({"status": "mission_paused_hold"})
        except Exception as e:
            return responses.err(f"pause_and_hold failed: {e}")

    @mcp.tool()
    async def set_velocity(
        forward_ms: float, right_ms: float, down_ms: float, yaw_deg_s: float = 0.0
    ) -> str:
        """Set body-frame velocity (requires offboard mode)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        speed = (forward_ms**2 + right_ms**2 + down_ms**2) ** 0.5
        if msg := limits.check_speed_m_s(speed):
            return responses.err(msg)
        try:
            from mavsdk.offboard import VelocityBodyYawspeed

            await mavsdk_client.get_drone().offboard.set_velocity_body(
                VelocityBodyYawspeed(forward_ms, right_ms, down_ms, yaw_deg_s)
            )
            return responses.ok(
                {
                    "forward_ms": forward_ms,
                    "right_ms": right_ms,
                    "down_ms": down_ms,
                    "yaw_deg_s": yaw_deg_s,
                }
            )
        except Exception as e:
            return responses.err(f"set_velocity failed: {e}")

    @mcp.tool()
    async def start_offboard() -> str:
        """Start offboard mode (required before set_velocity)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().offboard.start()
            return responses.ok({"offboard": True})
        except Exception as e:
            return responses.err(f"start_offboard failed: {e}")

    @mcp.tool()
    async def stop_offboard() -> str:
        """Stop offboard mode."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().offboard.stop()
            return responses.ok({"offboard": False})
        except Exception as e:
            return responses.err(f"stop_offboard failed: {e}")
