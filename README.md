# edge-ai-MCP

MAVSDK-only drone backend for the **SAR stack**. All flight I/O goes through MAVSDK (`Action`, `MissionRaw`, `Telemetry`). No raw MAVLink.

Used internally by **gateway → frontend LLM** via a drone-http compatible HTTP API on port **3001**.

## SAR stack (recommended)

```bash
cd /home/jetson/Code
./sar-stack.sh start proxy    # or: auto | serial
```

The **drone** tmux window runs `scripts/stack_server.py`:

| Port | Purpose |
|------|---------|
| **3001** | Gateway LLM tools + frontend telemetry (`DRONE_SERVER_URL`) |
| **8765** | MCP SSE (localhost only; gateway proxies `/mcp/*` with API key) |

Flow:

```
Frontend chat → gateway :3000/infer → LLM → POST :3001/v1/apply-tool → MAVSDK → FC

Hermes (external) → https://edge-ai.basilrari.com/mcp
                 → gateway (Bearer MCP_API_KEY) → 127.0.0.1:8765 → MAVSDK
```

## Prerequisites

```bash
cd MCP
pip install -r requirements.txt
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAVSDK_CONNECT` | `udpin://0.0.0.0:14550` | MAVSDK connection |
| `MCP_HTTP_PORT` | `3001` | HTTP API for gateway |
| `MCP_SSE_PORT` | `8765` | MCP SSE (bind `127.0.0.1` only) |
| `MCP_SSE_MOUNT_PATH` | `/mcp` | SSE path prefix for gateway proxy |
| `MCP_MIN_ALT_M` | `2` | Min altitude (m) |
| `MCP_MAX_ALT_M` | `120` | Max altitude (m) |
| `MCP_MAX_DISTANCE_M` | `2000` | Max horizontal distance from home (m) |
| `MCP_MAX_SPEED_M_S` | `15` | Max speed for offboard velocity |
| `MCP_MAX_WAYPOINTS` | `120` | Max waypoints per mission upload |

## Test from frontend chat

With sar-stack running, try in the dashboard:

- *"Just hover in place for now"*
- *"Return to home immediately"* (SITL / when safe)

## Test scripts

```bash
python3 scripts/test_unit.py
python3 scripts/test_sitl.py --skip-flight
```

## Mission upload (dashboard Mission Planner)

```json
{
  "include_takeoff": true,
  "takeoff_alt_m": 15,
  "include_rtl": true,
  "waypoints": [
    {"lat_deg": 23.558, "lon_deg": 120.473, "alt_m": 15}
  ]
}
```

Posted to `POST /v1/mission/upload` (proxied by gateway as `/drone/mission/upload`).

## Public MCP for Hermes (optional)

Set `MCP_API_KEY` in `sar-stack.env` and restart the stack. The gateway exposes:

- `GET/POST https://edge-ai.basilrari.com/mcp` — streamable HTTP (Hermes; requires auth)
- `GET https://edge-ai.basilrari.com/mcp/sse` — legacy SSE (requires auth)
- `POST https://edge-ai.basilrari.com/mcp/messages/` — MCP messages (requires auth)

**Auth:** `Authorization: Bearer <MCP_API_KEY>` or header `X-API-Key: <MCP_API_KEY>`.

### Cloudflare (your account)

If you already have a tunnel pointing **edge-ai.basilrari.com → localhost:3000** (gateway), you do **not** need a new tunnel, DNS record, or ingress rule. MCP is served on the same hostname under `/mcp/*`.

Optional hardening in the Cloudflare dashboard:

1. **Zero Trust → Access** — not required; API key is enforced by the gateway.
2. **Security → WAF** — optional rate limit on path `/mcp/*` to reduce abuse.
3. Keep the tunnel config unchanged unless you moved the gateway port.

### Hermes

1. Add MCP server URL: `https://edge-ai.basilrari.com/mcp` (not `/mcp/sse`)
2. Transport: SSE
3. Authentication: yes — paste the same `MCP_API_KEY` from `sar-stack.env`

Verify:

```bash
curl -sS -N -H "Authorization: Bearer $MCP_API_KEY" \
  https://edge-ai.basilrari.com/mcp/sse | head -5
```

You should see an `event: endpoint` line within a few seconds.

## Standalone stdio MCP (optional, local dev only)

Not started by sar-stack. For Cursor/debug on the Jetson:

```bash
python3 server.py
```

## Deploy

```bash
git remote -v   # git@github.com-edge-ai-mcp:basilrari/edge-ai-MCP.git
git push -u origin main
```
