#!/usr/bin/env python3
"""MAVSDK-only MCP server for ArduPilot (edge-ai-MCP)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without pip install -e .
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from mcp.server.fastmcp import FastMCP

from edge_ai_mcp import __version__
from edge_ai_mcp.tools import register_all_tools


def main() -> None:
    parser = argparse.ArgumentParser(description="MAVSDK Drone MCP Server (ArduPilot)")
    parser.add_argument(
        "--connect",
        default=None,
        help="Default MAVSDK connection (e.g. udpin://0.0.0.0:14550)",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport",
    )
    args = parser.parse_args()

    if args.connect:
        import os

        os.environ["MAVSDK_CONNECT"] = args.connect

    mcp = FastMCP(
        "edge-ai-mcp",
        instructions="""Control an ArduPilot drone via MAVSDK only (no raw MAVLink).

Connect first with connect() (default UDP 14550 listen).
Mission upload accepts JSON with a waypoints array (1–120 items).
Altitude, distance, and speed limits are enforced before flight commands.
""",
    )
    register_all_tools(mcp)

    print(f"edge-ai-mcp v{__version__} starting", file=sys.stderr)
    print(f"Transport: {args.transport}", file=sys.stderr)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
