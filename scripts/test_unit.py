#!/usr/bin/env python3
"""Smoke tests for limits and mission builder (no FC required)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from edge_ai_mcp import limits, mission_builder


def test_limits() -> None:
    assert limits.check_altitude_m(15) is None
    assert limits.check_altitude_m(1) is not None
    assert limits.check_altitude_m(200) is not None
    assert limits.check_waypoint_count(0) is not None
    assert limits.check_waypoint_count(3) is None


def test_mission_builder() -> None:
    raw = """{
      "include_takeoff": true,
      "takeoff_alt_m": 15,
      "include_rtl": true,
      "waypoints": [
        {"lat": 23.558, "lon": 120.473, "alt_m": 15},
        {"lat": 23.560, "lon": 120.475, "alt_m": 20}
      ]
    }"""
    parsed = mission_builder.parse_mission_json(raw, home_lat=23.557, home_lon=120.472)
    items = mission_builder.build_mission_items(parsed)
    assert len(items) >= 4  # home + takeoff + 2 wp + rtl
    assert parsed["waypoints"][0][0] == 23.558


if __name__ == "__main__":
    test_limits()
    test_mission_builder()
    print("unit smoke OK")
