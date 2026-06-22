"""drone-http compatible HTTP API for the SAR gateway and frontend."""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import mavsdk_client
from .telemetry_cache import get_cache
from .tool_dispatch import GATEWAY_TOOL_NAMES, apply_gateway_tool, upload_planner_mission

_flight_logs: deque[dict[str, Any]] = deque(maxlen=500)


def push_log(level: str, message: str) -> None:
    _flight_logs.append(
        {"ts_ms": int(time.time() * 1000), "level": level, "message": message}
    )


def create_http_app() -> Starlette:
    async def health(_: Request) -> JSONResponse:
        connected = mavsdk_client.is_connected()
        link = get_cache().link.to_dict()
        if not connected:
            link = {"kind": "disconnected", "display": "Waiting for MAVSDK", "url": ""}
        return JSONResponse(
            {
                "status": "ok",
                "mavlink_target_system": 1,
                "mavlink_target_component": 1,
                "known_tools": list(GATEWAY_TOOL_NAMES),
                "link": link,
                "backend": "edge-ai-mcp",
            }
        )

    async def position(_: Request) -> JSONResponse:
        c = get_cache()
        if c.lat_deg is None or c.lon_deg is None:
            return JSONResponse(
                {
                    "ok": False,
                    "lat_deg": None,
                    "lon_deg": None,
                    "alt_amsl_m": None,
                    "error": "no_global_position_yet",
                }
            )
        return JSONResponse(
            {
                "ok": True,
                "lat_deg": c.lat_deg,
                "lon_deg": c.lon_deg,
                "alt_amsl_m": c.alt_amsl_m,
                "error": None,
            }
        )

    async def telemetry(_: Request) -> JSONResponse:
        return JSONResponse(get_cache().snapshot())

    async def mission(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "current_seq": None, "waypoints": []})

    async def mission_upload(request: Request) -> JSONResponse:
        try:
            body = await request.json()
            count = await upload_planner_mission(body)
            push_log("info", f"mission upload: ok ({count} items)")
            return JSONResponse({"ok": True, "item_count": count}, status_code=200)
        except Exception as e:
            push_log("warn", f"mission upload FAIL: {e}")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

    async def mission_clear(_: Request) -> JSONResponse:
        try:
            await mavsdk_client.get_drone().mission_raw.clear_mission()
            push_log("info", "mission cleared")
            return JSONResponse({"ok": True})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)})

    async def logs(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "entries": list(_flight_logs)})

    async def logs_clear(_: Request) -> JSONResponse:
        _flight_logs.clear()
        return JSONResponse({"ok": True})

    async def mavlink_logs(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "entries": []})

    async def apply_tool(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"ok": False, "tool": "", "error": "invalid_json"},
                status_code=400,
            )
        tool = str(body.get("tool", ""))
        params = body.get("params", {})
        rid = request.headers.get("x-request-id", "")
        push_log("info", f"apply_tool: {tool} params={params} rid={rid}")
        try:
            await apply_gateway_tool(tool, params)
            push_log("info", f"OK: {tool}")
            return JSONResponse(
                {
                    "ok": True,
                    "tool": tool,
                    "error": None,
                    "target_system": 1,
                    "target_component": 1,
                }
            )
        except Exception as e:
            push_log("warn", f"FAIL {tool}: {e}")
            return JSONResponse(
                {
                    "ok": False,
                    "tool": tool,
                    "error": str(e),
                    "target_system": 1,
                    "target_component": 1,
                }
            )

    async def telemetry_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_text(json.dumps(get_cache().snapshot()))
                await asyncio.sleep(0.2)
        except WebSocketDisconnect:
            return
        except Exception:
            return

    async def logs_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                if _flight_logs:
                    await websocket.send_text(json.dumps(_flight_logs[-1]))
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return
        except Exception:
            return

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/v1/position", position, methods=["GET"]),
            Route("/v1/telemetry", telemetry, methods=["GET"]),
            Route("/v1/mission", mission, methods=["GET"]),
            Route("/v1/mission/upload", mission_upload, methods=["POST"]),
            Route("/v1/mission/clear", mission_clear, methods=["POST"]),
            Route("/v1/logs", logs, methods=["GET"]),
            Route("/v1/logs/clear", logs_clear, methods=["POST"]),
            Route("/v1/logs/mavlink", mavlink_logs, methods=["GET"]),
            Route("/v1/apply-tool", apply_tool, methods=["POST"]),
            WebSocketRoute("/v1/ws/telemetry", telemetry_ws),
            WebSocketRoute("/v1/ws/logs", logs_ws),
        ]
    )
