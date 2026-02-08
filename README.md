# Shelly Interface

<img src="https://raw.githubusercontent.com/getdoover/shelly-interface/main/assets/icon.png" alt="App Icon" style="max-width: 100px;">

**Allows other Doover apps to publish/receive configurable information to/from one or more Shelly products connected to a doovit via wifi.**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/getdoover/shelly-interface)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/getdoover/shelly-interface/blob/main/LICENSE)

[Getting Started](#getting-started) | [Configuration](#configuration) | [Developer](https://github.com/getdoover/shelly-interface/blob/main/DEVELOPMENT.md) | [Need Help?](#need-help)

<br/>

## Overview

Shelly Interface is a Doover device application that bridges Shelly smart home products with the Doover platform. It enables other Doover apps to monitor and control Shelly relays, switches, covers, lights, and inputs over the local network via wifi, without requiring cloud connectivity.

The application supports both Shelly Gen1 and Gen2+ (including Gen3) devices, automatically detecting the device generation and available components on startup. It uses the Shelly local HTTP API to poll device statuses, execute commands, and publish power consumption metrics -- all orchestrated through Doover's inter-app tag system.

Whether you need to automate relay switching based on sensor data from another Doover app, monitor power usage across multiple Shelly devices, or control roller shutters on a schedule, Shelly Interface provides the configurable middleware to make it happen.

### Features

- **Multi-device management** -- Configure and manage multiple Shelly devices from a single app instance
- **Gen1 and Gen2+ support** -- Automatic generation detection with appropriate API calls for each
- **Auto-component discovery** -- Automatically detects switches, inputs, covers, and lights on each device
- **Inter-app command/status tags** -- Other Doover apps can send commands and read statuses via configurable tag prefixes
- **Power data logging** -- Publishes power metrics (active power, voltage, current) to a data channel for historical logging
- **Configurable polling** -- Adjustable poll intervals, timeouts, and retry logic with exponential backoff
- **HTTP authentication** -- Optional per-device username/password authentication for secured Shelly devices
- **Component aliasing** -- Assign custom aliases to components for human-friendly tag names
- **Device inventory tag** -- Publishes a complete inventory of detected devices and their components
- **Resilient communication** -- Retry with exponential backoff, connection timeout handling, and per-device failure tracking

<br/>

## Getting Started

### Prerequisites

1. One or more Shelly devices (Gen1 or Gen2+) connected to the same local network as the doovit
2. The IP addresses or hostnames of each Shelly device
3. If HTTP authentication is enabled on any Shelly device, the corresponding username and password

### Installation

Add the Shelly Interface app to your doovit through the Doover platform. The app is available as a Docker device application and will be deployed automatically to your device.

### Quick Start

1. Add the app to your doovit
2. In the app configuration, add at least one device entry with a **Name** and **Host** (IP address)
3. Leave the **Components** array empty to enable auto-detection, or specify components manually
4. Deploy the configuration -- the app will start polling your Shelly devices immediately

<br/>

## Configuration

### Top-Level Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Devices** | List of Shelly devices to manage | *Required* |
| **Poll Interval** | Seconds between polling each device for status updates | `5.0` |
| **Command Tag Prefix** | Prefix for command tags that other apps write to trigger actions | `"cmd"` |
| **Status Tag Prefix** | Prefix for status tags published by this app | `"status"` |
| **Publish Power Data** | Whether to publish power metrics to a data channel for logging | `true` |
| **Power Publish Interval** | Minimum seconds between power data channel publishes | `60.0` |
| **Connection Timeout** | HTTP request timeout in seconds per device | `5.0` |
| **Retry Count** | Number of retries on failed device communication | `3` |
| **Auto Detect Components** | Auto-detect device components on startup via device info API | `true` |

### Device Settings

Each entry in the **Devices** array has the following fields:

| Setting | Description | Default |
|---------|-------------|---------|
| **Name** | Friendly name for the device (used in tag names) | *Required* |
| **Host** | IP address or hostname of the Shelly device | *Required* |
| **Auth User** | Username for HTTP auth (if device auth is enabled) | `""` |
| **Auth Password** | Password for HTTP auth (if device auth is enabled) | `""` |
| **Components** | Specific components to monitor/control (auto-detected if empty) | `[]` |

### Component Settings

Each entry in a device's **Components** array has the following fields:

| Setting | Description | Default |
|---------|-------------|---------|
| **Type** | Component type: `switch`, `input`, `cover`, or `light` | `"switch"` |
| **ID** | Component instance ID on the device | `0` |
| **Alias** | Custom alias for this component (used in tag names if set) | `""` |

### Example Configuration

```json
{
  "devices": [
    {
      "name": "Workshop Relay",
      "host": "192.168.1.50",
      "auth_user": "",
      "auth_password": "",
      "components": [
        { "type": "switch", "id": 0, "alias": "main_lights" },
        { "type": "switch", "id": 1, "alias": "exhaust_fan" }
      ]
    },
    {
      "name": "Garage Door",
      "host": "192.168.1.51",
      "auth_user": "admin",
      "auth_password": "secret",
      "components": []
    }
  ],
  "poll_interval": 5.0,
  "command_tag_prefix": "cmd",
  "status_tag_prefix": "status",
  "publish_power_data": true,
  "power_publish_interval": 60.0,
  "connection_timeout": 5.0,
  "retry_count": 3,
  "auto_detect_components": true
}
```

<br/>

## Tags

Shelly Interface communicates with other Doover apps via tags. Tag names follow the pattern `{prefix}_{device_name}_{component_type}_{component_id}`, or `{prefix}_{device_name}_{alias}` if an alias is set.

### Status Tags

Status tags are published by this app to report the current state of each component. The prefix is configurable (default: `status`).

| Tag Pattern | Description |
|-------------|-------------|
| **`status_{device}_{type}_{id}`** | Current status of a device component |
| **`device_inventory`** | Complete inventory of all detected devices, their generations, online status, and components |
| **`app_status`** | Aggregate app status with count of online/total devices and last poll timestamp |

#### Switch Status Fields

| Field | Description |
|-------|-------------|
| `online` | Whether the device is reachable |
| `output` | Current relay state (`true` = on, `false` = off) |
| `apower` | Active power in watts (Gen2+ only) |
| `voltage` | Voltage in volts (Gen2+ only) |
| `current` | Current in amps (Gen2+ only) |
| `temperature_c` | Device temperature in Celsius (Gen2+ only) |
| `errors` | Any reported errors (Gen2+ only) |
| `has_timer` | Whether a timer is active (Gen1 only) |
| `timer_remaining` | Seconds remaining on timer (Gen1 only) |
| `last_updated` | ISO 8601 timestamp of last update |

#### Input Status Fields

| Field | Description |
|-------|-------------|
| `online` | Whether the device is reachable |
| `state` | Current input state |
| `last_updated` | ISO 8601 timestamp of last update |

#### Cover Status Fields

| Field | Description |
|-------|-------------|
| `online` | Whether the device is reachable |
| `state` | Current cover state (e.g., `open`, `closed`, `opening`, `closing`) |
| `current_pos` | Current position percentage |
| `apower` | Active power in watts |
| `last_updated` | ISO 8601 timestamp of last update |

#### Light Status Fields

| Field | Description |
|-------|-------------|
| `online` | Whether the device is reachable |
| `output` | Current light state (`true` = on, `false` = off) |
| `brightness` | Brightness level (if supported) |
| `last_updated` | ISO 8601 timestamp of last update |

### Command Tags

Command tags are written by other Doover apps to trigger actions on Shelly devices. The prefix is configurable (default: `cmd`). After processing, command tags are automatically cleared.

| Tag Pattern | Description |
|-------------|-------------|
| **`cmd_{device}_{type}_{id}`** | Send a command to a specific device component |

#### Switch Commands

```json
{ "action": "set", "value": true }
{ "action": "set", "value": true, "toggle_after": 10 }
{ "action": "toggle" }
```

#### Cover Commands

```json
{ "action": "open" }
{ "action": "close" }
{ "action": "stop" }
```

#### Light Commands

```json
{ "action": "set", "value": true }
{ "action": "toggle" }
```

### Data Channels

| Channel | Description |
|---------|-------------|
| **`power_data`** | Power metrics (active power, voltage, current) per device/component, published at the configured interval |

<br/>

## How It Works

1. **Initialization** -- On startup, the app creates an HTTP session and loads configured devices. If auto-detection is enabled, it queries each Shelly device to determine its generation (Gen1 vs Gen2+) and discovers available components (switches, inputs, covers, lights).

2. **Command Processing** -- Each loop iteration, the app checks for pending command tags written by other Doover apps. When a command is found (e.g., `{"action": "set", "value": true}`), it sends the corresponding HTTP request to the Shelly device and then clears the command tag.

3. **Status Polling** -- The app polls all configured devices for their current state using the appropriate API (Gen1: `/relay/{id}`, `/light/{id}`; Gen2+: `/rpc/Shelly.GetStatus`). Status data including output state, power metrics, and error information is published to status tags.

4. **Power Data Publishing** -- If enabled, the app periodically aggregates power metrics (active power, voltage, current) from all switch components and publishes them to the `power_data` channel for historical logging and analysis.

5. **App Status Update** -- At the end of each loop, the app publishes an aggregate `app_status` tag containing the count of online vs total devices and the last poll timestamp.

6. **Retry and Recovery** -- All HTTP communication includes configurable retry logic with exponential backoff. Devices that become unreachable are marked offline, and the app continues attempting to reconnect on subsequent polling cycles.

<br/>

## Integrations

This device app works with:

- **Shelly Gen1 devices** -- Shelly 1, Shelly 1PM, Shelly 2.5, Shelly Dimmer, and other Gen1 products via the `/settings`, `/relay`, and `/light` HTTP APIs
- **Shelly Gen2+ devices** -- Shelly Plus, Shelly Pro, Shelly Mini, and Gen3 products via the `/rpc/Shelly.GetStatus`, `/rpc/Switch.Set`, `/rpc/Cover.Open`, and `/rpc/Light.Set` RPC APIs
- **Other Doover apps** -- Any Doover application can interact with Shelly devices by reading status tags and writing command tags using the configurable tag prefix system
- **Doover data channels** -- Power metrics are published to the `power_data` channel for integration with dashboards, alerts, and historical data analysis

<br/>

## Need Help?

- Email: support@doover.com
- [Doover Documentation](https://docs.doover.com)
- [App Developer Documentation](https://github.com/getdoover/shelly-interface/blob/main/DEVELOPMENT.md)

<br/>

## Version History

### v0.1.0 (Current)
- Initial release
- Multi-device management with Gen1 and Gen2+ support
- Auto-detection of device generation and components
- Inter-app command and status tag system
- Power data channel publishing with configurable intervals
- HTTP authentication support
- Retry with exponential backoff
- Component aliasing for human-friendly tag names

<br/>

## License

This app is licensed under the [Apache License 2.0](https://github.com/getdoover/shelly-interface/blob/main/LICENSE).
