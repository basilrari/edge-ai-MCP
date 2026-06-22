# edge-ai-MCP

MAVSDK-only MCP server for **ArduPilot** drone control. No raw MAVLink — all I/O through MAVSDK plugins (`Action`, `MissionRaw`, `Telemetry`).

## Prerequisites

- Python 3.10+
- MAVSDK Python (`mavsdk`, `grpcio`)
- ArduPilot SITL or FC reachable via MAVSDK (default `udpin://0.0.0.0:14550`)

```bash
pip install -r requirements.txt
# or: pip install -e .
```

## Run (stdio MCP)

```bash
cd MCP
python3 server.py
python3 server.py --connect udpin://0.0.0.0:14550
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAVSDK_CONNECT` | `udpin://0.0.0.0:14550` | Default connection string |
| `MCP_MIN_ALT_M` | `2` | Min altitude (m) |
| `MCP_MAX_ALT_M` | `120` | Max altitude (m) |
| `MCP_MAX_DISTANCE_M` | `2000` | Max horizontal distance from home (m) |
| `MCP_MAX_SPEED_M_S` | `15` | Max speed for offboard velocity |
| `MCP_MAX_WAYPOINTS` | `120` | Max waypoints per mission upload |

## Mission upload (multi-waypoint)

```json
{
  "include_takeoff": true,
  "takeoff_alt_m": 15,
  "include_rtl": true,
  "waypoints": [
    {"lat": 23.558, "lon": 120.473, "alt_m": 15},
    {"lat": 23.560, "lon": 120.475, "alt_m": 20}
  ]
}
```

Use MCP tool `upload_mission` or `upload_and_start_mission` with this JSON string.

## Tools

**Connection:** `connect`, `disconnect`, `is_connected`, `get_link_status`

**Flight:** `arm`, `disarm`, `takeoff`, `land`, `return_to_launch`, `hold`, `goto_location`, `pause_and_hold`, `emergency_stop`, offboard velocity helpers

**Mission:** `upload_mission`, `upload_and_start_mission`, `clear_mission`, `start_mission`, `pause_mission`, `resume_mission`, `set_mission_current`, `get_mission_progress`

**Telemetry:** `get_telemetry`, `get_battery`, `get_flight_mode`

**Peripherals:** gimbal/camera (if hardware supports MAVSDK plugins)

## Tests

```bash
python3 scripts/test_unit.py
# SITL must be on 14550; stop drone-http if it binds the same port
python3 scripts/test_sitl.py
python3 scripts/test_sitl.py --skip-flight   # connect-only
```

## Hermes example

```bash
hermes mcp add drone --command ssh --args jetson@HOST "cd ~/Code/MCP && python3 server.py"
```

## Port conflict

Only one process can listen on UDP **14550**. When testing MCP directly, stop `drone-http` in sar-stack or run SITL on another forwarded port.

## Deploy key (Jetson → GitHub)

```bash
git remote -v   # git@github.com-edge-ai-mcp:basilrari/edge-ai-MCP.git
git push -u origin main
```
