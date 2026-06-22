# edge-ai-MCP

MAVSDK-only drone control for **ArduPilot**. No raw MAVLink — all I/O through MAVSDK plugins (`Action`, `MissionRaw`, `Telemetry`).

Used by the **SAR stack** on the Jetson: gateway LLM tools and frontend telemetry go through the local HTTP API on port **3001** (`DRONE_SERVER_URL`). External MCP / Hermes / public exposure is **not** enabled (add later if needed).

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt`
- ArduPilot SITL or FC via MAVSDK (default `udpin://0.0.0.0:14550`)

## SAR stack (recommended)

```bash
cd /home/jetson/Code
./sar-stack.sh start proxy    # or: auto | serial
```

The **drone** tmux window runs `scripts/stack_server.py`:

- Listens on **3001** (`/v1/apply-tool`, `/v1/telemetry`, mission upload, WebSockets)
- Gateway uses `DRONE_SERVER_URL=http://127.0.0.1:3001`
- Frontend chat → gateway `/infer` → LLM → apply-tool on this service

## Standalone (dev)

**Gateway-compatible HTTP only:**

```bash
python3 scripts/stack_server.py --http-port 3001
```

**stdio MCP** (local Cursor on the Jetson, optional):

```bash
python3 server.py
```

## Tests

```bash
python3 scripts/test_unit.py
python3 scripts/test_sitl.py --skip-flight
```

Stop `drone-http` or any other process on UDP **14550** before direct MCP/MAVSDK tests.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAVSDK_CONNECT` | `udpin://0.0.0.0:14550` | MAVSDK connection |
| `MCP_HTTP_PORT` | `3001` | Local HTTP API (gateway) |
| `MCP_MIN_ALT_M` / `MCP_MAX_ALT_M` | `2` / `120` | Altitude limits (m) |
| `MCP_MAX_DISTANCE_M` | `2000` | Max distance from home (m) |
| `MCP_MAX_SPEED_M_S` | `15` | Max offboard speed |
| `MCP_MAX_WAYPOINTS` | `120` | Mission upload cap |

## Mission JSON (MCP tools / MissionRaw)

```json
{
  "include_takeoff": true,
  "takeoff_alt_m": 15,
  "include_rtl": true,
  "waypoints": [
    {"lat": 23.558, "lon": 120.473, "alt_m": 15}
  ]
}
```

Dashboard Mission Planner uses `POST /v1/mission/upload` with `lat_deg` / `lon_deg` / `alt_m` waypoints.

## Git

```bash
git remote -v   # git@github.com-edge-ai-mcp:basilrari/edge-ai-MCP.git
```
