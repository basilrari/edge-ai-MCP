#!/usr/bin/env python3
"""Integration smoke test against ArduPilot SITL via MAVSDK (UDP 14550).

Prerequisites:
  - ArduPilot SITL or mavlink-router forwarding to UDP 14550
  - drone-http NOT bound to 14550 (stop sar-stack drone window or use another port)

Usage:
  cd MCP && python3 scripts/test_sitl.py
  MCP_CONNECT=udpin://0.0.0.0:14550 python3 scripts/test_sitl.py --skip-flight
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from edge_ai_mcp import config, limits, mission_builder, mavsdk_client


async def run(skip_flight: bool) -> int:
    connect = os.environ.get("MCP_CONNECT", config.DEFAULT_CONNECT)
    print(f"Connecting to {connect}...")

    try:
        await mavsdk_client.connect(connect)
    except Exception as e:
        print(f"FAIL connect: {e}")
        return 1

    pos = await mavsdk_client.current_position()
    print(f"OK connected position={pos}")

    if skip_flight:
        await mavsdk_client.disconnect()
        print("SKIP flight/mission (--skip-flight)")
        return 0

    # Limits rejection
    if limits.check_altitude_m(500) is None:
        print("FAIL limits should reject 500m alt")
        return 1
    print("OK limits reject high altitude")

    home = await mavsdk_client.home_position()
    if pos is None and home is None:
        print("WARN no position/home yet; skipping mission upload")
        await mavsdk_client.disconnect()
        return 0

    base_lat = (home or pos)[0]
    base_lon = (home or pos)[1]
    mission_json = json.dumps(
        {
            "include_takeoff": True,
            "takeoff_alt_m": 15,
            "include_rtl": True,
            "waypoints": [
                {"lat": base_lat + 0.0001, "lon": base_lon + 0.0001, "alt_m": 15},
                {"lat": base_lat + 0.0002, "lon": base_lon + 0.0001, "alt_m": 15},
            ],
        }
    )
    try:
        parsed = mission_builder.parse_mission_json(
            mission_json,
            home_lat=home[0] if home else None,
            home_lon=home[1] if home else None,
        )
        origin = await mavsdk_client.origin_for_limits()
        if origin and (msg := mission_builder.validate_mission_distances(
            limits.Position(*origin), parsed
        )):
            print(f"FAIL mission distance: {msg}")
            return 1
        items = mission_builder.build_mission_items(parsed)
        drone = mavsdk_client.get_drone()
        await drone.mission_raw.upload_mission(items)
        print(f"OK mission uploaded ({len(items)} items)")
    except Exception as e:
        print(f"WARN mission upload: {e} (SITL may need GUIDED/arm first)")

    try:
        telem = await drone.telemetry.position().__anext__()
        print(f"OK telemetry lat={telem.latitude_deg:.6f} mode check next")
    except Exception as e:
        print(f"WARN telemetry: {e}")

    await mavsdk_client.disconnect()
    print("OK disconnect")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-flight", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.skip_flight)))


if __name__ == "__main__":
    main()
