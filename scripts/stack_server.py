#!/usr/bin/env python3
"""SAR stack: MAVSDK HTTP API (:3001) for gateway + MCP SSE (:8765) for Hermes."""

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
from edge_ai_mcp.http_server import create_http_app, push_log, start_mavlink_logger
from edge_ai_mcp.tools import register_all_tools


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        "edge-ai-mcp",
        host=config.MCP_SSE_HOST,
        port=config.MCP_SSE_PORT,
        instructions="ArduPilot drone control via MAVSDK. Alt/distance/speed limits enforced.",
    )
    register_all_tools(mcp)
    return mcp


def combine_mcp_apps(sse_app, stream_app):
    """Merge SSE + streamable HTTP; streamable lifespan initializes its task group."""
    from starlette.applications import Starlette

    return Starlette(
        routes=[*sse_app.routes, *stream_app.routes],
        lifespan=stream_app.router.lifespan_context,
    )


async def run_stack(http_port: int, connect: str) -> None:
    os.environ.setdefault("MAVSDK_CONNECT", connect)
    push_log("info", f"edge-ai-mcp stack v{__version__} starting")

    try:
        await mavsdk_client.connect(connect)
        push_log("info", f"MAVSDK connected: {connect}")
    except Exception as e:
        push_log("warn", f"MAVSDK connect failed (will retry on tool call): {e}")

    telemetry_cache.start_poller()
    start_mavlink_logger()

    mcp = build_mcp()
    mcp_app = combine_mcp_apps(
        mcp.sse_app(mount_path=config.MCP_SSE_MOUNT_PATH),
        mcp.streamable_http_app(),
    )

    http_cfg = Config(create_http_app(), host="0.0.0.0", port=http_port, log_level="info")
    sse_cfg = Config(mcp_app, host=config.MCP_SSE_HOST, port=config.MCP_SSE_PORT, log_level="info")

    print(
        f"edge-ai-mcp: HTTP :{http_port} (gateway/frontend), "
        f"MCP 127.0.0.1:{config.MCP_SSE_PORT} "
        f"(streamable /mcp + SSE /sse for gateway /mcp/* proxy)",
        file=sys.stderr,
    )

    await asyncio.gather(Server(http_cfg).serve(), Server(sse_cfg).serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="edge-ai-MCP SAR stack server")
    parser.add_argument("--http-port", type=int, default=config.MCP_HTTP_PORT)
    parser.add_argument("--connect", default=config.DEFAULT_CONNECT)
    args = parser.parse_args()
    asyncio.run(run_stack(args.http_port, args.connect))


if __name__ == "__main__":
    main()
