"""Shared MAVSDK connection state."""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from mavsdk import System

from . import config

_drone: Optional[System] = None
_connected = False
_connection_string = config.DEFAULT_CONNECT


def connection_string() -> str:
    return _connection_string


def is_connected() -> bool:
    return _connected and _drone is not None


def get_drone() -> System:
    if not is_connected() or _drone is None:
        raise RuntimeError("Not connected. Call connect() first.")
    return _drone


async def connect(addr: str | None = None) -> None:
    global _drone, _connected, _connection_string

    if _connected and _drone is not None:
        raise RuntimeError("Already connected. Call disconnect() first.")

    target = addr or config.DEFAULT_CONNECT
    _connection_string = target
    _drone = System()
    await _drone.connect(system_address=target)

    print(f"Connecting to {target}...", file=sys.stderr)

    async with asyncio.timeout(config.CONNECT_TIMEOUT_S):
        async for state in _drone.core.connection_state():
            if state.is_connected:
                break

        async for health in _drone.telemetry.health():
            if health.is_global_position_ok or health.is_home_position_ok:
                break

    _connected = True


async def disconnect() -> None:
    global _drone, _connected
    _drone = None
    _connected = False


async def current_position() -> tuple[float, float] | None:
    if not is_connected() or _drone is None:
        return None
    try:
        pos = await _drone.telemetry.position().__anext__()
        return pos.latitude_deg, pos.longitude_deg
    except Exception:
        return None


async def home_position() -> tuple[float, float] | None:
    if not is_connected() or _drone is None:
        return None
    try:
        async with asyncio.timeout(3):
            home = await _drone.telemetry.home().__anext__()
            return home.latitude_deg, home.longitude_deg
    except Exception:
        return None


async def origin_for_limits() -> tuple[float, float] | None:
    """Prefer home, then current position, for distance checks."""
    home = await home_position()
    if home is not None:
        return home
    return await current_position()
