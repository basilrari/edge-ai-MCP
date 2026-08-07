"""MCP tool registration."""

from mcp.server.fastmcp import FastMCP

from edge_ai_mcp.tools.connection import register_connection_tools
from edge_ai_mcp.tools.flight import register_flight_tools
from edge_ai_mcp.tools.mission import register_mission_tools
from edge_ai_mcp.tools.peripherals import register_peripheral_tools
from edge_ai_mcp.tools.telemetry import register_telemetry_tools


def register_all_tools(mcp: FastMCP) -> None:
    register_connection_tools(mcp)
    register_flight_tools(mcp)
    register_mission_tools(mcp)
    register_telemetry_tools(mcp)
    register_peripheral_tools(mcp)
