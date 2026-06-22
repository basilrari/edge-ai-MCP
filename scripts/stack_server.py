#!/usr/bin/env python3
"""SAR stack entry: MAVSDK connect + drone-http API + MCP SSE for external clients."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from mcp.server.fastmcp import FastMCP
from uvicorn import Config, Server

from edge_ai_mcp import __version__, config
from edge_ai_mcp import mavsdk_client, telemetry_cache
from edge_ai_mcp.http_server import create_http_app, push_log
from edge_ai_mcp.tools import register_all_tools


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        "edge-ai-mcp",
        host=config.MCP_SSE_HOST,
        port=config.MCP_SSE_PORT,
        instructions="""ArduPilot drone control via MAVSDK (edge-ai-MCP).
Auto-connected when started via stack_server. Alt/distance/speed limits enforced.""",
    )
    register_all_tools(mcp)
    return mcp


async def run_stack(http_port: int, connect: str) -> None:
    os.environ.setdefault("MAVSDK_CONNECT", connect)
    push_log("info", f"edge-ai-mcp stack v{__version__} starting")

    try:
        await mavsdk_client.connect(connect)
        push_log("info", f"MAVSDK connected: {connect}")
    except Exception as e:
        push_log("warn", f"MAVSDK connect failed (will retry on tool call): {e}")

    telemetry_cache.start_poller()

    http_app = create_http_app()
    mcp = build_mcp()
    sse_app = mcp.sse_app(mount_path=config.MCP_SSE_MOUNT_PATH)

    http_cfg = Config(http_app, host="0.0.0.0", port=http_port, log_level="info")
    sse_cfg = Config(sse_app, host=config.MCP_SSE_HOST, port=config.MCP_SSE_PORT, log_level="info")

    http_server = Server(http_cfg)
    sse_server = Server(sse_cfg)

    print(
        f"edge-ai-mcp stack: HTTP :{http_port} (gateway/frontend), "
        f"MCP SSE {config.MCP_SSE_HOST}:{config.MCP_SSE_PORT}",
        file=sys.stderr,
    )

    await asyncio.gather(http_server.serve(), sse_server.serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="edge-ai-MCP SAR stack server")
    parser.add_argument(
        "--http-port",
        type=int,
        default=int(os.environ.get("MCP_HTTP_PORT", "3001")),
    )
    parser.add_argument(
        "--connect",
        default=os.environ.get("MAVSDK_CONNECT", config.DEFAULT_CONNECT),
    )
    args = parser.parse_args()
    asyncio.run(run_stack(args.http_port, args.connect))


if __name__ == "__main__":
    main()
