# Build Plan

## App Summary
- Name: shelly-interface
- Type: docker
- Description: Bridge app that allows other Doover apps to publish/receive configurable information to/from one or more Shelly products (relays, switches, power meters, etc.) connected to a doovit via local WiFi network.

## External Integration
- Service: Shelly local HTTP API (Gen1 and Gen2/Gen3 devices)
- Documentation:
  - Gen2+ API: https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/
  - Gen1 API: https://shelly-api-docs.shelly.cloud/gen1/
  - mDNS Discovery: https://shelly-api-docs.shelly.cloud/gen2/General/mDNS/
- Authentication: HTTP Basic Auth (Gen1) or digest auth (Gen2) when enabled on device; many devices run with auth disabled on LAN

### Shelly API Summary

**Gen2+ (RPC over HTTP):**
- Device info: `GET http://<ip>/rpc/Shelly.GetDeviceInfo`
- Full status: `GET http://<ip>/rpc/Shelly.GetStatus`
- Switch status: `GET http://<ip>/rpc/Switch.GetStatus?id=<n>`
- Switch set: `GET http://<ip>/rpc/Switch.Set?id=<n>&on=true|false`
- Switch toggle: `GET http://<ip>/rpc/Switch.Toggle?id=<n>`

**Gen1 (HTTP endpoints):**
- Device info: `GET http://<ip>/shelly`
- Status: `GET http://<ip>/status`
- Relay control: `GET http://<ip>/relay/<n>?turn=on|off|toggle`
- Relay status: `GET http://<ip>/relay/<n>`

**Device Discovery (mDNS):**
- Service type: `_shelly._tcp` (Gen2+) and `_http._tcp` (both generations)
- TXT records include: `gen=2|3`, `app`, `ver`
- Gen1 hostnames follow pattern: `shelly<model>-<MAC>`

**Switch Status Response Fields (Gen2):**
- `output` (boolean): relay on/off state
- `apower` (number): active power in watts
- `voltage` (number): supply voltage
- `current` (number): current in amps
- `temperature.tC` / `temperature.tF`: device temperature
- `errors` (array): `overtemp`, `overpower`, `overvoltage`, `undervoltage`

**Gen1 Relay Status Response:**
- `ison` (boolean): relay state
- `has_timer` (boolean): timer active
- `timer_remaining` (number): seconds left on timer

## Data Flow
- **Inputs**:
  - Configuration from Doover (list of Shelly devices with IP addresses, component types, and polling settings)
  - Commands from other Doover apps via tags (e.g., `set_relay_0_on`, `toggle_relay_1`)
  - Shelly device status data read via local HTTP API
- **Processing**:
  - Poll each configured Shelly device at configurable intervals
  - Detect device generation (Gen1 vs Gen2+) via `/shelly` endpoint or mDNS TXT records
  - Read device status (relay state, power metrics, temperature, errors)
  - Process commands from other Doover apps (set relay states, toggle, etc.)
  - Translate between Doover tag format and Shelly HTTP API calls
  - Handle device connectivity errors gracefully (device offline, timeout, auth failure)
- **Outputs**:
  - Per-device status tags for other Doover apps to read (relay states, power data, error states)
  - Aggregate status tag with all device states
  - App-level status tag (online device count, errors, last poll time)
  - Channel publishing for historical data logging (power metrics over time)

## Configuration Schema
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `devices` | Array(Object) | yes | `[]` | List of Shelly devices to manage |
| `devices[].name` | String | yes | - | Friendly name for the device (used in tag names) |
| `devices[].host` | String | yes | - | IP address or hostname of the Shelly device |
| `devices[].auth_user` | String | no | `""` | Username for HTTP auth (if device auth is enabled) |
| `devices[].auth_pass` | String | no | `""` | Password for HTTP auth (if device auth is enabled) |
| `devices[].components` | Array(Object) | no | `[]` | Specific components to monitor/control (auto-detected if empty) |
| `devices[].components[].type` | Enum | yes | - | Component type: `switch`, `input`, `cover`, `light` |
| `devices[].components[].id` | Integer | yes | `0` | Component instance ID on the device |
| `devices[].components[].alias` | String | no | - | Custom alias for this component (used in tag names if set) |
| `poll_interval` | Number | no | `5.0` | Seconds between polling each device for status updates |
| `command_tag_prefix` | String | no | `"cmd"` | Prefix for command tags that other apps write to trigger actions |
| `status_tag_prefix` | String | no | `"status"` | Prefix for status tags published by this app |
| `publish_power_data` | Boolean | no | `true` | Whether to publish power metrics to a data channel for logging |
| `power_publish_interval` | Number | no | `60.0` | Minimum seconds between power data channel publishes |
| `connection_timeout` | Number | no | `5.0` | HTTP request timeout in seconds per device |
| `retry_count` | Integer | no | `3` | Number of retries on failed device communication |
| `auto_detect_components` | Boolean | no | `true` | Auto-detect device components on startup via device info API |

## UI Elements

No UI elements required (has_ui: false).

This app acts as a backend bridge. Other Doover apps with UI can read this app's tags via `config.Application` references and `get_tag(tag_name, app_key=shelly_interface_key)`.

## Documentation Chunks

### Required Chunks
- `config-schema.md` - Configuration types and patterns (arrays, objects, enums for device list config)
- `docker-application.md` - Application class structure (setup, main_loop lifecycle)
- `docker-project.md` - Entry point and Dockerfile

### Recommended Chunks
- `tags-channels.md` - Essential for inter-app communication (other apps read Shelly state via tags, send commands via tags)
- `docker-advanced.md` - Throttling patterns for API rate limiting, error recovery patterns for device connectivity
- `doover-config.md` - App metadata configuration

### Discovery Keywords
relay, switch, power, voltage, current, temperature, poll, http, wifi, device, bridge, interface, command, status, throttle, timeout, retry, channel, publish, tag, inter-agent

## Implementation Notes

### Architecture
- The app runs a main loop that:
  1. Checks for pending commands from other apps (via command tags)
  2. Executes any pending commands against Shelly devices
  3. Polls all configured Shelly devices for status
  4. Updates status tags so other Doover apps can read device states
  5. Optionally publishes power metrics to a data channel

### Device Communication
- Use `aiohttp` (async HTTP client) for non-blocking communication with Shelly devices
- Detect device generation on first connection by calling `/shelly` endpoint (both Gen1 and Gen2 support this)
  - Response with `"gen": 2` or `"gen": 3` indicates Gen2+ (use RPC API)
  - Response without `gen` field indicates Gen1 (use legacy HTTP API)
- Cache device generation info to avoid repeated detection
- Handle device authentication when `auth_user` / `auth_pass` are configured

### Tag Naming Convention
- Status tags: `{status_tag_prefix}_{device_name}_{component_type}_{component_id}` (e.g., `status_living_room_switch_0`)
- Command tags: `{command_tag_prefix}_{device_name}_{component_type}_{component_id}` (e.g., `cmd_living_room_switch_0`)
- Command format: `{"action": "set", "value": true}` or `{"action": "toggle"}` or `{"action": "set", "value": false, "toggle_after": 30}`
- After executing a command, clear the command tag to `null`

### Error Handling
- Device offline: Set device status tag to `{"online": false, "error": "connection_timeout", "last_seen": "..."}` and log warning
- Auth failure: Set status to `{"online": false, "error": "auth_failed"}` and log error
- Use retry logic with exponential backoff between retries
- Continue polling other devices even if one device fails

### Inter-App Communication Pattern
- Other apps reference this app via `config.Application("Shelly Interface App Key")`
- They read status: `self.get_tag("status_living_room_switch_0", app_key=shelly_key)`
- They send commands: `self.set_tag("cmd_living_room_switch_0", {"action": "set", "value": true})`
- This app processes commands each loop iteration and clears processed command tags

### External Packages Needed
- `aiohttp` - Async HTTP client for communicating with Shelly devices over local network

### Main Loop
- `loop_target_period = 2` (poll every ~2 seconds for responsive relay control)
- Each iteration: process commands first, then poll device statuses
- Use throttling for power data channel publishing (separate from status tag updates)

### Auto-Detection Flow
- On startup (in `setup()` or first `main_loop()`), if `auto_detect_components` is true:
  1. Call `/shelly` on each device to detect generation
  2. For Gen2+: call `Shelly.GetStatus` to enumerate components
  3. For Gen1: call `/settings` to discover relay count and device type
  4. Store detected components in memory and use them for polling
  5. Set a tag with the detected device inventory

### State Management
- No complex state machine needed; simple operational states tracked via tags:
  - App status: `app_status` tag with `{"state": "running", "devices_online": N, "devices_total": M, "last_poll": "..."}`
  - Per-device status updated each poll cycle
