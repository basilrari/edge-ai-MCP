"""Environment configuration."""

import os

DEFAULT_CONNECT = os.environ.get("MAVSDK_CONNECT", "udpin://0.0.0.0:14550")
CONNECT_TIMEOUT_S = float(os.environ.get("MAVSDK_CONNECT_TIMEOUT_S", "20"))
MCP_HTTP_PORT = int(os.environ.get("MCP_HTTP_PORT", "3001"))
MCP_SSE_HOST = os.environ.get("MCP_SSE_HOST", "0.0.0.0")
MCP_SSE_PORT = int(os.environ.get("MCP_SSE_PORT", "8765"))
MCP_SSE_MOUNT_PATH = os.environ.get("MCP_SSE_MOUNT_PATH", "/mcp")
TELEMETRY_POLL_S = float(os.environ.get("MCP_TELEMETRY_POLL_S", "0.2"))

MIN_ALT_M = float(os.environ.get("MCP_MIN_ALT_M", "2"))
MAX_ALT_M = float(os.environ.get("MCP_MAX_ALT_M", "120"))
MAX_DISTANCE_M = float(os.environ.get("MCP_MAX_DISTANCE_M", "2000"))
MAX_SPEED_M_S = float(os.environ.get("MCP_MAX_SPEED_M_S", "15"))
MAX_WAYPOINTS = int(os.environ.get("MCP_MAX_WAYPOINTS", "120"))

DEFAULT_TAKEOFF_ALT_M = float(os.environ.get("MCP_DEFAULT_TAKEOFF_ALT_M", "15"))
