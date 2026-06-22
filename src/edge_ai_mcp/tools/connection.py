"""Connection MCP tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import config, mavsdk_client, responses


def register_connection_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def connect(connection_string: str = config.DEFAULT_CONNECT) -> str:
        """Connect to the flight controller via MAVSDK.

        Args:
            connection_string: e.g. udpin://0.0.0.0:14550 or serial:///dev/ttyACM0:115200
        """
        try:
            await mavsdk_client.connect(connection_string)
            return responses.ok({"connection": mavsdk_client.connection_string()})
        except Exception as e:
            return responses.err(str(e))

    @mcp.tool()
    async def disconnect() -> str:
        """Disconnect from the flight controller."""
        await mavsdk_client.disconnect()
        return responses.ok({"disconnected": True})

    @mcp.tool()
    async def is_connected() -> str:
        """Return whether MAVSDK is connected."""
        return responses.ok({"connected": mavsdk_client.is_connected()})

    @mcp.tool()
    async def get_link_status() -> str:
        """Connection string, armed state, and flight mode."""
        if not mavsdk_client.is_connected():
            return responses.err("Not connected. Call connect() first.")
        try:
            drone = mavsdk_client.get_drone()
            armed = await drone.telemetry.armed().__anext__()
            mode = await drone.telemetry.flight_mode().__anext__()
            pos = await mavsdk_client.current_position()
            home = await mavsdk_client.home_position()
            return responses.ok(
                {
                    "connection": mavsdk_client.connection_string(),
                    "armed": armed,
                    "flight_mode": str(mode),
                    "position": {"lat": pos[0], "lon": pos[1]} if pos else None,
                    "home": {"lat": home[0], "lon": home[1]} if home else None,
                }
            )
        except Exception as e:
            return responses.err(str(e))
