# Drone MAVSDK MCP Server

MCP (Model Context Protocol) server for drone control via MAVSDK.

Connects to PX4/ArduPilot flight controllers and exposes drone operations as MCP tools.

## Architecture

```
MCP Client (Hermes/Claude) <--> stdio/SSE --> MCP Server --> MAVSDK --> mavsdk_server --> MAVLink --> PX4/ArduPilot
```

## Tools (38 total)

### Connection
- `connect` - Connect to flight controller (UDP/Serial)
- `disconnect` - Disconnect from flight controller
- `is_connected` - Check connection health

### Arming
- `arm` - Arm motors
- `disarm` - Disarm motors
- `is_armed` - Check arm status

### Flight
- `takeoff` - Take off to altitude
- `land` - Land at current position
- `return_to_launch` - RTL and land
- `hold` - Hold position (loiter)
- `emergency_stop` - Kill motors immediately

### Navigation
- `goto_location` - Fly to lat/lon/alt
- `set_velocity` - Body-frame velocity (offboard mode)
- `start_offboard` - Start offboard mode
- `stop_offboard` - Stop offboard mode

### Telemetry
- `get_telemetry` - Position, attitude, battery, flight mode
- `get_battery` - Battery voltage and remaining
- `get_flight_mode` - Current flight mode
- `set_flight_mode` - Set flight mode

### Missions
- `upload_mission` - Upload waypoint mission
- `start_mission` - Start mission execution
- `pause_mission` - Pause mission

### Gimbal
- `gimbal_set_angles` - Set gimbal pitch/yaw/roll
- `gimbal_take_control` - Take gimbal control
- `gimbal_release_control` - Release gimbal control
- `gimbal_point_at_location` - Point gimbal at GPS location (ROI)
- `gimbal_get_attitude` - Get current gimbal angles

### Camera
- `camera_take_photo` - Take a photo
- `camera_start_recording` - Start video recording
- `camera_stop_recording` - Stop video recording
- `camera_set_mode` - Switch photo/video mode
- `camera_get_mode` - Get current camera mode
- `camera_zoom_in` - Zoom in
- `camera_zoom_out` - Zoom out
- `camera_zoom_stop` - Stop zoom
- `camera_get_storage` - Get storage status

### Landing Gear
- `landing_gear_deploy` - Deploy (extend) landing gear
- `landing_gear_retract` - Retract landing gear (in-flight only)

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
- `mavsdk` -- MAVSDK Python bindings
- `mcp` -- Model Context Protocol SDK
- `grpcio>=1.75.0` -- gRPC for MAVSDK backend

## Hermes MCP Config

Added via:
```bash
hermes mcp add drone --command ssh --args jetson@140.123.105.214 "cd ~/Code/MCP && python3 server.py"
```

## Note on Serial Connection

For direct connection to Pixhawk via USB:
```bash
python3 server.py --connect serial:///dev/ttyUSB0:57600
```

On Jetson Orin, the serial device may be /dev/ttyTHS1 or /dev/ttyUSB0 depending on wiring.
