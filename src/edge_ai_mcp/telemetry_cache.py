"""In-memory telemetry cache polled from MAVSDK (drone-http compatible shape)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from . import config, mavsdk_client


@dataclass
class LinkInfo:
    kind: str = "mavsdk"
    display: str = "MAVSDK"
    url: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "display": self.display, "url": self.url}


@dataclass
class TelemetryCache:
    link: LinkInfo = field(default_factory=LinkInfo)
    lat_deg: float | None = None
    lon_deg: float | None = None
    alt_amsl_m: float | None = None
    alt_rel_m: float | None = None
    groundspeed_m_s: float | None = None
    heading_deg: int | None = None
    roll_deg: float | None = None
    pitch_deg: float | None = None
    yaw_deg: float | None = None
    armed: bool | None = None
    mode: str | None = None
    home_lat_deg: float | None = None
    home_lon_deg: float | None = None
    home_alt_m: float | None = None
    battery_voltage_v: float | None = None
    battery_remaining_pct: int | None = None

    def snapshot(self) -> dict[str, Any]:
        ts_ms = int(time.time() * 1000)
        ok = self.lat_deg is not None and self.lon_deg is not None
        body: dict[str, Any] = {
            "ok": ok,
            "link": self.link.to_dict(),
            "ts_ms": ts_ms,
        }
        for key in (
            "lat_deg",
            "lon_deg",
            "alt_amsl_m",
            "alt_rel_m",
            "groundspeed_m_s",
            "heading_deg",
            "roll_deg",
            "pitch_deg",
            "yaw_deg",
            "armed",
            "mode",
            "home_lat_deg",
            "home_lon_deg",
            "home_alt_m",
            "battery_voltage_v",
            "battery_remaining_pct",
        ):
            val = getattr(self, key)
            if val is not None:
                body[key] = val
        return body


_cache = TelemetryCache()
_poller_task: asyncio.Task | None = None


def get_cache() -> TelemetryCache:
    return _cache


async def _poll_once() -> None:
    if not mavsdk_client.is_connected():
        _cache.link = LinkInfo(
            kind="disconnected",
            display="Waiting for MAVSDK",
            url="",
        )
        return

    _cache.link = LinkInfo(
        kind="mavsdk",
        display="MAVSDK connected",
        url=mavsdk_client.connection_string(),
    )
    drone = mavsdk_client.get_drone()

    try:
        pos = await asyncio.wait_for(drone.telemetry.position().__anext__(), timeout=2)
        _cache.lat_deg = pos.latitude_deg
        _cache.lon_deg = pos.longitude_deg
        _cache.alt_amsl_m = getattr(pos, "absolute_altitude_m", None)
        _cache.alt_rel_m = getattr(pos, "relative_altitude_m", None)
    except Exception:
        pass

    try:
        gs = await asyncio.wait_for(drone.telemetry.groundspeed().__anext__(), timeout=1)
        _cache.groundspeed_m_s = gs.groundspeed_m_s
    except Exception:
        pass

    try:
        att = await asyncio.wait_for(drone.telemetry.attitude_euler().__anext__(), timeout=1)
        _cache.roll_deg = att.roll_deg
        _cache.pitch_deg = att.pitch_deg
        _cache.yaw_deg = att.yaw_deg
    except Exception:
        pass

    try:
        armed = await asyncio.wait_for(drone.telemetry.armed().__anext__(), timeout=1)
        _cache.armed = armed
    except Exception:
        pass

    try:
        mode = await asyncio.wait_for(drone.telemetry.flight_mode().__anext__(), timeout=1)
        _cache.mode = str(mode)
    except Exception:
        pass

    try:
        home = await asyncio.wait_for(drone.telemetry.home().__anext__(), timeout=1)
        _cache.home_lat_deg = home.latitude_deg
        _cache.home_lon_deg = home.longitude_deg
        _cache.home_alt_m = getattr(home, "absolute_altitude_m", None)
    except Exception:
        pass

    try:
        bat = await asyncio.wait_for(drone.telemetry.battery().__anext__(), timeout=1)
        _cache.battery_voltage_v = bat.voltage_v
        _cache.battery_remaining_pct = int(bat.remaining_percent)
    except Exception:
        pass


async def _poll_loop() -> None:
    interval = float(getattr(config, "TELEMETRY_POLL_S", 0.2))
    while True:
        try:
            await _poll_once()
        except Exception:
            pass
        await asyncio.sleep(interval)


def start_poller() -> None:
    global _poller_task
    if _poller_task is None or _poller_task.done():
        _poller_task = asyncio.create_task(_poll_loop())


async def stop_poller() -> None:
    global _poller_task
    if _poller_task is not None:
        _poller_task.cancel()
        try:
            await _poller_task
        except asyncio.CancelledError:
            pass
        _poller_task = None
