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
_mavlink_msgs: deque[dict[str, Any]] = deque(maxlen=800)

_mavlink_logger_task: asyncio.Task | None = None


def push_log(level: str, message: str) -> None:
    entry = {"ts_ms": int(time.time() * 1000), "level": level, "message": message}
    _flight_logs.append(entry)




def mavlink_row_from_raw(
    message_name: str,
    fields_json: str,
    *,
    ts_ms: int,
    sys_id: int | None = None,
    comp_id: int | None = None,
) -> dict[str, Any]:
    """Shape expected by edge-ai-frontend (msg_id, msg_name, value)."""
    import json as _json

    msg_id = 0
    msg_name = message_name or "UNKNOWN"
    value = fields_json
    try:
        fields = _json.loads(fields_json) if isinstance(fields_json, str) else fields_json
        if isinstance(fields, dict):
            mid = fields.get("message_id", fields.get("msg_id"))
            if mid is not None:
                msg_id = int(mid)
            msg_name = str(fields.get("message_name", message_name) or message_name)
            parts: list[str] = []
            for key in sorted(fields.keys()):
                if key in ("message_id", "message_name", "msg_id"):
                    continue
                parts.append(f"{key}={fields[key]}")
            if parts:
                value = " ".join(parts)
    except Exception:
        value = str(fields_json)
    row: dict[str, Any] = {
        "ts_ms": ts_ms,
        "msg_id": msg_id,
        "msg_name": msg_name,
        "value": value,
    }
    if sys_id is not None:
        row["sys_id"] = sys_id
    if comp_id is not None:
        row["comp_id"] = comp_id
    return row

def push_mavlink_msg(msg: dict[str, Any]) -> None:
    _mavlink_msgs.append(msg)


def log_snapshot() -> dict[str, Any]:
    return {
        "type": "snapshot",
        "flight": list(_flight_logs),
        "mavlink": list(_mavlink_msgs),
    }


def start_mavlink_logger() -> None:
    """Subscribe to all incoming MAVLink messages, rate-limited, and store in _mavlink_msgs."""
    global _mavlink_logger_task
    if _mavlink_logger_task is not None and not _mavlink_logger_task.done():
        return  # already running

    async def _capture_loop():
        while True:
            try:
                if not mavsdk_client.is_connected():
                    await asyncio.sleep(1)
                    continue

                drone = mavsdk_client.get_drone()
                md = drone.mavlink_direct

                # Subscribe to specific message types (avoids "all messages" queue backup)
                WANTED_MESSAGES = [
                    "HEARTBEAT",
                    "STATUSTEXT",
                    "MISSION_CURRENT",
                    "MISSION_ITEM_REACHED",
                    "COMMAND_ACK",
                    "SYS_STATUS",
                    "BATTERY_STATUS",
                    "HOME_POSITION",
                    "AHRS2",
                    "AHRS",
                    "EKF_STATUS_REPORT",
                    "VIBRATION",
                    "NAV_CONTROLLER_OUTPUT",
                    "SERVO_OUTPUT_RAW",
                    "RC_CHANNELS",
                    "POWER_STATUS",
                    "MEMINFO",
                    "EXTENDED_SYS_STATE",
                    "HWSTATUS",
                    "TERRAIN_REPORT",
                    "GLOBAL_POSITION_INT",
                    "ATTITUDE",
                    "VFR_HUD",
                    "GPS_RAW_INT",
                ]

                async def _subscribe(name: str) -> None:
                    # Rate limit for high-frequency telemetry messages
                    high_rate = name in {"ATTITUDE", "VFR_HUD", "AHRS2", "GPS_RAW_INT", "GLOBAL_POSITION_INT"}
                    last_ts = 0.0
                    try:
                        async for raw in md.message(name):
                            if high_rate:
                                now = time.time()
                                if now - last_ts < 1.0:
                                    continue
                                last_ts = now
                            push_mavlink_msg(
                                mavlink_row_from_raw(
                                    raw.message_name,
                                    raw.fields_json,
                                    ts_ms=int(time.time() * 1000),
                                    sys_id=raw.system_id,
                                    comp_id=raw.component_id,
                                )
                            )
                    except Exception:
                        pass

                # Run all subscriptions concurrently
                tasks = [asyncio.create_task(_subscribe(n)) for n in WANTED_MESSAGES]
                await asyncio.gather(*tasks)
            except Exception:
                await asyncio.sleep(1)

    _mavlink_logger_task = asyncio.create_task(_capture_loop())


def stop_mavlink_logger() -> None:
    global _mavlink_logger_task
    if _mavlink_logger_task is not None:
        _mavlink_logger_task.cancel()
        _mavlink_logger_task = None


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

    async def logs_clear(request: Request) -> JSONResponse:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        target = body.get("target", "all") if isinstance(body, dict) else "all"
        if target in ("flight", "all"):
            _flight_logs.clear()
        if target in ("mavlink", "all"):
            _mavlink_msgs.clear()
        return JSONResponse({"ok": True})

    async def logs_snapshot(_: Request) -> JSONResponse:
        return JSONResponse(log_snapshot())

    async def mavlink_logs(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "entries": list(_mavlink_msgs)})

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
            # Send full snapshot on connect
            await websocket.send_text(json.dumps(log_snapshot()))
            last_flight_idx = len(_flight_logs)
            last_mavlink_idx = len(_mavlink_msgs)

            while True:
                # Check for new flight log entries
                current_flight_len = len(_flight_logs)
                while last_flight_idx < current_flight_len:
                    entry = list(_flight_logs)[last_flight_idx]
                    await websocket.send_text(json.dumps({
                        "type": "flight",
                        "entry": entry,
                    }))
                    last_flight_idx += 1

                # Check for new MAVLink entries
                current_mavlink_len = len(_mavlink_msgs)
                while last_mavlink_idx < current_mavlink_len:
                    entry = list(_mavlink_msgs)[last_mavlink_idx]
                    await websocket.send_text(json.dumps({
                        "type": "mavlink",
                        "entry": entry,
                    }))
                    last_mavlink_idx += 1

                await asyncio.sleep(0.2)
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
            Route("/v1/logs/snapshot", logs_snapshot, methods=["GET"]),
            Route("/v1/apply-tool", apply_tool, methods=["POST"]),
            WebSocketRoute("/v1/ws/telemetry", telemetry_ws),
            WebSocketRoute("/v1/ws/logs", logs_ws),
        ]
    )
