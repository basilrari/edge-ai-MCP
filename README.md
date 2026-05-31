# 🚁 Drone MAVSDK MCP Server

MCP (Model Context Protocol) server for drone control via MAVSDK.

Connects to PX4/ArduPilot flight controllers and exposes drone operations as MCP tools — usable by any MCP client (Hermes, Claude, etc.).

## Architecture

```
MCP Client (Hermes/Claude) ←→ stdio/SSE → MCP Server → MAVSDK → mavsdk_server → MAVLink → PX4/ArduPilot
```

## Tools

| Tool | Description |
|------|-------------|
| `connect` | Connect to flight controller (UDP/Serial) |
| `disconnect` | Disconnect from flight controller |
| `is_connected` | Check connection health |
| `arm` | Arm motors |
| `disarm` | Disarm motors |
| `is_armed` | Check arm status |
| `takeoff` | Take off to altitude |
| `land` | Land at current position |
| `return_to_launch` | RTL and land |
| `hold` | Hold position (loiter) |
| `emergency_stop` | Kill motors immediately |
| `goto_location` | Fly to lat/lon/alt |
| `set_velocity` | Body-frame velocity (offboard mode) |
| `start_offboard` | Start offboard mode |
| `stop_offboard` | Stop offboard mode |
| `get_telemetry` | Position, attitude, battery, flight mode |
| `get_battery` | Battery voltage and remaining |
| `get_flight_mode` | Current flight mode |
| `set_flight_mode` | Set flight mode |
| `upload_mission` | Upload waypoint mission |
| `start_mission` | Start mission execution |
| `pause_mission` | Pause mission |

## Usage

```bash
# stdio mode (for MCP clients)
python3 server.py

# With custom connection
python3 server.py --connect udp://192.168.1.10:14550

# SSE mode (HTTP)
python3 server.py --transport sse
```

## Dependencies

- Python 3.10+
- `mavsdk` — MAVSDK Python bindings
- `mcp` — Model Context Protocol SDK
- `grpcio>=1.75.0` — gRPC for MAVSDK backend

## Hermes MCP Config

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  drone:
    command: python3
    args: ["/home/jetson/Code/MCP/server.py"]
```
