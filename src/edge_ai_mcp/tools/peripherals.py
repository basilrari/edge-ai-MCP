"""Gimbal and camera MCP tools (MAVSDK plugins only)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import mavsdk_client, responses


def register_peripheral_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def gimbal_take_control() -> str:
        """Take gimbal control."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().gimbal.take_control()
            return responses.ok({"gimbal_control": True})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def gimbal_release_control() -> str:
        """Release gimbal control."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().gimbal.release_control()
            return responses.ok({"gimbal_control": False})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def gimbal_set_angles(
        pitch_deg: float = 0.0, yaw_deg: float = 0.0, roll_deg: float = 0.0
    ) -> str:
        """Set gimbal angles in degrees."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().gimbal.set_angles(pitch_deg, yaw_deg, roll_deg)
            return responses.ok(
                {"pitch_deg": pitch_deg, "yaw_deg": yaw_deg, "roll_deg": roll_deg}
            )
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def camera_take_photo() -> str:
        """Trigger camera shutter."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().camera.take_photo()
            return responses.ok({"photo": True})
        except Exception as e:
            return responses.err(str(e))
