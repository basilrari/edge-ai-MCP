# edge-ai-MCP

MAVSDK-only MCP server for **ArduPilot** drone control. No raw MAVLink — all I/O through MAVSDK plugins (`Action`, `MissionRaw`, `Telemetry`).

Integrated with the **SAR stack**: replaces `drone-http` MAVLink on port **3001** so the frontend LLM prompt → gateway → `/v1/apply-tool` uses MAVSDK with param limits.

## Prerequisites

- Python 3.10+
- MAVSDK Python (`mavsdk`, `grpcio`)
- ArduPilot SITL or FC reachable via MAVSDK (default `udpin://0.0.0.0:14550`)

```bash
pip install -r requirements.txt
```

## SAR stack (recommended — always on)

```bash
cd /home/jetson/Code
./sar-stack.sh start proxy    # or: auto | serial
```

The **drone** tmux window runs `scripts/stack_server.py`:

| Service | Port | Purpose |
|---------|------|---------|
| HTTP API | **3001** | Gateway LLM tools + frontend telemetry (`DRONE_SERVER_URL`) |
| MCP SSE | **8765** | Hermes / Cursor / external MCP clients |

Gateway proxies MCP publicly at:

`https://edge-ai.basilrari.com/mcp/sse`

## Run standalone

**stdio MCP** (Cursor / local):

```bash
cd MCP
python3 server.py
```

**SAR-compatible HTTP + MCP SSE** (manual):

```bash
python3 scripts/stack_server.py --http-port 3001 --connect udpin://0.0.0.0:14550
```

## Test from frontend chat

With sar-stack running, open the dashboard and try:

- *"Just hover in place for now"*
- *"What is the drone armed state?"* (informational — may return none)
- *"Return to home immediately"* (SITL only when safe)

The gateway calls `POST http://127.0.0.1:3001/v1/apply-tool` on edge-ai-MCP (same contract as legacy drone-http).

## Test scripts

```bash
python3 scripts/test_unit.py
python3 scripts/test_sitl.py --skip-flight
```

## External MCP (Hermes)

Public (via Cloudflare tunnel + gateway proxy):

```bash
# SSE endpoint (after tunnel is up)
https://edge-ai.basilrari.com/mcp/sse
```

Local:

```bash
http://127.0.0.1:8765/sse
```

**Hermes** (from your laptop):

```bash
hermes mcp add edge-drone --url https://edge-ai.basilrari.com/mcp/sse
```

When asked **"Does this server require authentication?"** → answer **`n`** (no API key is configured).

If connect times out, ensure sar-stack is running and the drone window was restarted after the latest MCP update (SSE must advertise `/mcp/messages/`, not `/messages/`).

**MCP Inspector** (local):

```bash
npx @modelcontextprotocol/inspector python3 server.py
```

**Cursor** (`~/.cursor/mcp.json` on a machine that can reach the Jetson):

```json
{
  "mcpServers": {
    "edge-ai-drone": {
      "url": "https://edge-ai.basilrari.com/mcp/sse"
    }
  }
}
```

Or SSH stdio:

```bash
hermes mcp add drone --command ssh --args jetson@HOST "cd ~/Code/MCP && python3 server.py"
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAVSDK_CONNECT` | `udpin://0.0.0.0:14550` | MAVSDK connection |
| `MCP_HTTP_PORT` | `3001` | drone-http compatible API |
| `MCP_SSE_PORT` | `8765` | MCP SSE for external clients |
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

Use MCP tool `upload_mission` or dashboard Mission Planner → `POST /v1/mission/upload`.

## Tools

**Gateway LLM tools** (via HTTP): `arm`, `takeoff`, `goto_location`, `start_mission`, `hover`, `return_to_home`, `land_immediately`, `mission_interrupt`, `mission_resume`, …

**MCP tools** (stdio/SSE): full catalog including `connect`, `get_telemetry`, `upload_mission`, gimbal/camera, etc.

## Deploy

```bash
git remote -v   # git@github.com-edge-ai-mcp:basilrari/edge-ai-MCP.git
git push -u origin main
```
