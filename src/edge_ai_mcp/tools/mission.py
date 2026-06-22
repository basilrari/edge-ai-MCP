"""Mission MCP tools (MAVSDK MissionRaw plugin)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import limits, mission_builder, mavsdk_client, responses


async def _upload_parsed(parsed: dict) -> tuple[int, str | None]:
    origin = await mavsdk_client.origin_for_limits()
    if origin is None:
        return 0, "Need home or current position for distance check"
    if msg := mission_builder.validate_mission_distances(
        limits.Position(*origin), parsed
    ):
        return 0, msg
    items = mission_builder.build_mission_items(parsed)
    await mavsdk_client.get_drone().mission_raw.upload_mission(items)
    return len(parsed["waypoints"]), None


def register_mission_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def upload_mission(waypoints_json: str) -> str:
        """Upload a multi-waypoint mission (MAVSDK MissionRaw, ArduPilot-shaped).

        JSON: {include_takeoff, takeoff_alt_m, include_rtl, waypoints:[{lat,lon,alt_m}, ...]}
        """
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            home = await mavsdk_client.home_position()
            parsed = mission_builder.parse_mission_json(
                waypoints_json,
                home_lat=home[0] if home else None,
                home_lon=home[1] if home else None,
            )
            count, err = await _upload_parsed(parsed)
            if err:
                return responses.err(err)
            return responses.ok({"waypoint_count": count, "item_count": len(mission_builder.build_mission_items(parsed))})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def upload_and_start_mission(waypoints_json: str) -> str:
        """Upload mission JSON then start execution."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            home = await mavsdk_client.home_position()
            parsed = mission_builder.parse_mission_json(
                waypoints_json,
                home_lat=home[0] if home else None,
                home_lon=home[1] if home else None,
            )
            count, err = await _upload_parsed(parsed)
            if err:
                return responses.err(err)
            await mavsdk_client.get_drone().mission_raw.start_mission()
            return responses.ok({"waypoint_count": count, "status": "mission_started"})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def clear_mission() -> str:
        """Clear the onboard mission."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().mission_raw.clear_mission()
            return responses.ok({"cleared": True})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def start_mission() -> str:
        """Start the uploaded mission."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().mission_raw.start_mission()
            return responses.ok({"status": "mission_started"})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def pause_mission() -> str:
        """Pause the running mission."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().mission_raw.pause_mission()
            return responses.ok({"status": "mission_paused"})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def resume_mission() -> str:
        """Resume a paused mission (MissionRaw start)."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().mission_raw.start_mission()
            return responses.ok({"status": "mission_resumed"})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def set_mission_current(seq: int) -> str:
        """Set current mission item index."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            await mavsdk_client.get_drone().mission_raw.set_current_mission_item(seq)
            return responses.ok({"current_seq": seq})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def get_mission_progress() -> str:
        """Get current mission progress."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            progress = await mavsdk_client.get_drone().mission_raw.mission_progress().__anext__()
            finished = await mavsdk_client.get_drone().mission_raw.is_mission_finished().__anext__()
            return responses.ok(
                {
                    "current": progress.current,
                    "total": progress.total,
                    "finished": finished,
                }
            )
        except Exception as e:
            return responses.err(str(e))
