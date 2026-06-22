"""Environment configuration."""

import os

DEFAULT_CONNECT = os.environ.get("MAVSDK_CONNECT", "udpin://0.0.0.0:14550")
CONNECT_TIMEOUT_S = float(os.environ.get("MAVSDK_CONNECT_TIMEOUT_S", "20"))

MIN_ALT_M = float(os.environ.get("MCP_MIN_ALT_M", "2"))
MAX_ALT_M = float(os.environ.get("MCP_MAX_ALT_M", "120"))
MAX_DISTANCE_M = float(os.environ.get("MCP_MAX_DISTANCE_M", "2000"))
MAX_SPEED_M_S = float(os.environ.get("MCP_MAX_SPEED_M_S", "15"))
MAX_WAYPOINTS = int(os.environ.get("MCP_MAX_WAYPOINTS", "120"))

DEFAULT_TAKEOFF_ALT_M = float(os.environ.get("MCP_DEFAULT_TAKEOFF_ALT_M", "15"))
