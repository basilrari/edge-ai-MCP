"""Telemetry MCP tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import mavsdk_client, responses


def register_telemetry_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_telemetry() -> str:
        """Position, attitude, battery, flight mode, armed, health."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            drone = mavsdk_client.get_drone()
            pos = await drone.telemetry.position().__anext__()
            att = await drone.telemetry.attitude_euler().__anext__()
            bat = await drone.telemetry.battery().__anext__()
            mode = await drone.telemetry.flight_mode().__anext__()
            armed = await drone.telemetry.armed().__anext__()
            health = await drone.telemetry.health().__anext__()
            return responses.ok(
                {
                    "position": {
                        "lat": pos.latitude_deg,
                        "lon": pos.longitude_deg,
                        "alt_amsl_m": pos.absolute_altitude_m,
                        "alt_rel_m": pos.relative_altitude_m,
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
                    "flight_mode": str(mode),
                    "armed": armed,
                    "health": {
                        "global_position_ok": health.is_global_position_ok,
                        "armable": health.is_armable,
                        "home_position_ok": health.is_home_position_ok,
                    },
                }
            )
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def get_battery() -> str:
        """Battery voltage and remaining percent."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            bat = await mavsdk_client.get_drone().telemetry.battery().__anext__()
            return responses.ok(
                {
                    "voltage_v": bat.voltage_v,
                    "remaining_pct": round(bat.remaining_percent * 100, 1),
                }
            )
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def get_flight_mode() -> str:
        """Current flight mode string."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            mode = await mavsdk_client.get_drone().telemetry.flight_mode().__anext__()
            return responses.ok({"flight_mode": str(mode)})
        except Exception as e:
            return responses.err(str(e))
