# AppGen State

## Current Phase
Phase 6 - Document

## Status
completed

## App Details
- **Name:** shelly-interface
- **Description:** Allows other Doover apps to publish/receive configurable information to/from one or more Shelly products (including relays etc) connected to a doovit via wifi
- **App Type:** docker
- **Has UI:** false
- **Container Registry:** ghcr.io/getdoover
- **Target Directory:** /home/sid/shelly-interface
- **GitHub Repo:** getdoover/shelly-interface
- **Repo Visibility:** public
- **GitHub URL:** https://github.com/getdoover/shelly-interface
- **Icon URL:** https://raw.githubusercontent.com/getdoover/shelly-interface/main/assets/icon.png

## Completed Phases
- [x] Phase 1: Creation - 2026-02-08T21:35:48Z
- [x] Phase 2: Docker Config - 2026-02-09T07:37:00Z
  - UI removed (has_ui: false): removed app_ui.py, cleaned application.py
  - Icon validated and converted from SVG to 256x256 PNG, stored in assets/icon.png
  - doover_config.json restructured for Docker device app (type: DEV, image_name, build_args)
- [x] Phase 3: Docker Plan - 2026-02-09T08:15:00Z
  - Researched Shelly Gen1 and Gen2+ local HTTP API documentation
  - Designed configuration schema for multi-device management
  - Defined inter-app tag naming conventions for commands and status
  - Created PLAN.md with complete build plan including external API details
  - No user questions needed (description was sufficiently clear)
  - External package needed: aiohttp
- [x] Phase 4: Docker Build - 2026-02-09T09:30:00Z
  - Generated app_config.py with full configuration schema (devices array with nested components, polling/timing settings, tag prefixes, power publishing, connection settings, auto-detection)
  - Generated application.py with ShellyDevice class and ShellyInterfaceApplication (Gen1/Gen2+ detection, auto-component discovery, command processing, status polling, power data channel publishing, retry with exponential backoff)
  - Removed unused app_state.py (no state machine needed per plan)
  - Added aiohttp as production dependency, removed unused transitions dependency
  - Updated doover_config.json via export-config
  - Updated simulators/app_config.json with matching sample config
- [x] Phase 5: Docker Check - 2026-02-09T10:00:00Z
  - All validation checks passed
  - Dependencies (uv sync): PASS - 22 packages audited, all resolved
  - Imports: PASS - `from shelly_interface.application import *` succeeded
  - Config Schema (doover config-schema export): PASS - schema validated successfully
  - File Structure: PASS - __init__.py, application.py, app_config.py all present (no app_ui.py expected, has_ui=false)
- [x] Phase 6: Document - 2026-02-09T10:30:00Z
  - Generated comprehensive README.md with all required sections
  - Documented 9 top-level config settings, 5 device settings, 3 component settings
  - Documented 3 status tags (per-component, device_inventory, app_status) with field details for switch/input/cover/light
  - Documented command tags for switch/cover/light with JSON examples
  - Documented power_data data channel

## References
- **Has References:** false

## User Decisions
- App name: shelly-interface
- Description: Allows other Doover apps to publish/receive configurable information to/from one or more Shelly products (including relays etc) connected to a doovit via wifi
- GitHub repo: getdoover/shelly-interface
- App type: docker
- Has UI: false
- Has references: false
- Icon URL: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/shelly.svg

## Next Action
Phase 6 complete. README.md generated with full documentation.
