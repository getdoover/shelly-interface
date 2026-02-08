import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import aiohttp

from pydoover.docker import Application

from .app_config import ShellyInterfaceConfig

log = logging.getLogger(__name__)


class ShellyDevice:
    """Represents a single Shelly device with cached generation info and components."""

    def __init__(self, name: str, host: str, auth_user: str = "", auth_pass: str = ""):
        self.name = name
        self.host = host
        self.auth_user = auth_user
        self.auth_pass = auth_pass

        # Detected at runtime
        self.generation: int | None = None  # 1, 2, or 3
        self.components: list[dict] = []  # [{"type": "switch", "id": 0, "alias": ""}]
        self.online: bool = False
        self.last_seen: str | None = None
        self.last_error: str | None = None
        self.consecutive_failures: int = 0

    @property
    def auth(self) -> aiohttp.BasicAuth | None:
        if self.auth_user:
            return aiohttp.BasicAuth(self.auth_user, self.auth_pass)
        return None

    def tag_name_for_component(self, component: dict, prefix: str) -> str:
        """Generate a tag name for a component.

        Format: {prefix}_{device_name}_{component_type}_{component_id}
        Uses alias instead of type_id if alias is set.
        """
        device_slug = self.name.lower().replace(" ", "_")
        alias = component.get("alias", "")
        if alias:
            return f"{prefix}_{device_slug}_{alias.lower().replace(' ', '_')}"
        return f"{prefix}_{device_slug}_{component['type']}_{component['id']}"


class ShellyInterfaceApplication(Application):
    config: ShellyInterfaceConfig

    loop_target_period = 2  # Poll every ~2 seconds for responsive relay control

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.devices: list[ShellyDevice] = []
        self.session: aiohttp.ClientSession | None = None
        self.last_power_publish_time: float = 0
        self.initialized: bool = False

    async def setup(self):
        """Initialize HTTP session and parse device configuration."""
        timeout = aiohttp.ClientTimeout(
            total=self.config.connection_timeout.value or 5.0
        )
        self.session = aiohttp.ClientSession(timeout=timeout)

        self._load_devices_from_config()

        log.info(
            f"Shelly Interface initialized with {len(self.devices)} device(s) configured"
        )

    def _load_devices_from_config(self):
        """Parse device list from configuration."""
        self.devices = []
        if not self.config.devices.elements:
            log.warning("No devices configured")
            return

        for device_elem in self.config.devices.elements:
            # Extract device fields from the object element
            fields = {}
            for child in device_elem.elements:
                fields[child.x_name] = child.value

            name = fields.get("name", "")
            host = fields.get("host", "")
            if not name or not host:
                log.warning(f"Skipping device with missing name or host: {fields}")
                continue

            dev = ShellyDevice(
                name=name,
                host=host,
                auth_user=fields.get("auth_user", "") or "",
                auth_pass=fields.get("auth_password", "") or "",
            )

            # Parse explicitly configured components
            components_elem = None
            for child in device_elem.elements:
                if child.x_name == "components":
                    components_elem = child
                    break

            if components_elem and components_elem.elements:
                for comp_elem in components_elem.elements:
                    comp_fields = {}
                    for child in comp_elem.elements:
                        comp_fields[child.x_name] = child.value
                    if comp_fields.get("type"):
                        dev.components.append({
                            "type": comp_fields["type"],
                            "id": comp_fields.get("id", 0) or 0,
                            "alias": comp_fields.get("alias", "") or "",
                        })

            self.devices.append(dev)

        log.info(f"Loaded {len(self.devices)} device(s) from configuration")

    async def main_loop(self):
        """Main loop: detect devices, process commands, poll statuses, publish data."""
        # Auto-detect components on first run
        if not self.initialized:
            await self._auto_detect_all_devices()
            self.initialized = True

        # Step 1: Process pending commands from other apps
        await self._process_commands()

        # Step 2: Poll all device statuses
        await self._poll_all_devices()

        # Step 3: Publish power data to channel (throttled)
        if self.config.publish_power_data.value:
            await self._publish_power_data_throttled()

        # Step 4: Update app-level status tag
        await self._update_app_status()

    # -------------------------------------------------------------------------
    # Device Detection
    # -------------------------------------------------------------------------

    async def _auto_detect_all_devices(self):
        """Detect generation and components for all configured devices."""
        for device in self.devices:
            await self._detect_device(device)

        # Publish detected device inventory
        inventory = {}
        for dev in self.devices:
            inventory[dev.name] = {
                "host": dev.host,
                "generation": dev.generation,
                "online": dev.online,
                "components": dev.components,
            }
        await self.set_tag("device_inventory", inventory)

    async def _detect_device(self, device: ShellyDevice):
        """Detect a device's generation and auto-detect components if needed."""
        try:
            # Both Gen1 and Gen2+ support /shelly endpoint
            data = await self._http_get(device, "/shelly")
            if data is None:
                log.warning(f"Device {device.name} ({device.host}) not reachable")
                device.online = False
                device.last_error = "connection_timeout"
                return

            device.online = True
            device.last_seen = datetime.now(timezone.utc).isoformat()
            device.last_error = None

            # Detect generation
            gen = data.get("gen")
            if gen and int(gen) >= 2:
                device.generation = int(gen)
            else:
                device.generation = 1

            log.info(
                f"Device {device.name} ({device.host}) detected as Gen{device.generation}"
            )

            # Auto-detect components if none explicitly configured
            auto_detect = self.config.auto_detect_components.value
            if auto_detect and not device.components:
                await self._auto_detect_components(device)

        except Exception as e:
            log.error(f"Error detecting device {device.name}: {e}")
            device.online = False
            device.last_error = str(e)

    async def _auto_detect_components(self, device: ShellyDevice):
        """Auto-detect components from a device."""
        if device.generation >= 2:
            await self._auto_detect_gen2(device)
        else:
            await self._auto_detect_gen1(device)

        log.info(
            f"Device {device.name}: detected {len(device.components)} component(s): "
            f"{device.components}"
        )

    async def _auto_detect_gen2(self, device: ShellyDevice):
        """Auto-detect components for Gen2+ devices using Shelly.GetStatus."""
        data = await self._http_get(device, "/rpc/Shelly.GetStatus")
        if data is None:
            return

        # Enumerate switch components
        for key in data:
            if key.startswith("switch:"):
                comp_id = int(key.split(":")[1])
                device.components.append({
                    "type": "switch",
                    "id": comp_id,
                    "alias": "",
                })
            elif key.startswith("input:"):
                comp_id = int(key.split(":")[1])
                device.components.append({
                    "type": "input",
                    "id": comp_id,
                    "alias": "",
                })
            elif key.startswith("cover:"):
                comp_id = int(key.split(":")[1])
                device.components.append({
                    "type": "cover",
                    "id": comp_id,
                    "alias": "",
                })
            elif key.startswith("light:"):
                comp_id = int(key.split(":")[1])
                device.components.append({
                    "type": "light",
                    "id": comp_id,
                    "alias": "",
                })

    async def _auto_detect_gen1(self, device: ShellyDevice):
        """Auto-detect components for Gen1 devices using /settings."""
        data = await self._http_get(device, "/settings")
        if data is None:
            return

        # Detect relays
        relays = data.get("relays", [])
        for i in range(len(relays)):
            device.components.append({
                "type": "switch",
                "id": i,
                "alias": "",
            })

        # Detect lights (e.g. Shelly Dimmer)
        lights = data.get("lights", [])
        for i in range(len(lights)):
            device.components.append({
                "type": "light",
                "id": i,
                "alias": "",
            })

    # -------------------------------------------------------------------------
    # Command Processing
    # -------------------------------------------------------------------------

    async def _process_commands(self):
        """Check and execute pending commands from other apps via command tags."""
        cmd_prefix = self.config.command_tag_prefix.value or "cmd"

        for device in self.devices:
            if not device.online and not device.components:
                continue

            for component in device.components:
                tag_name = device.tag_name_for_component(component, cmd_prefix)
                command = self.get_tag(tag_name)

                if command is None:
                    continue

                log.info(
                    f"Processing command for {device.name} "
                    f"{component['type']}:{component['id']}: {command}"
                )

                try:
                    await self._execute_command(device, component, command)
                except Exception as e:
                    log.error(
                        f"Error executing command on {device.name} "
                        f"{component['type']}:{component['id']}: {e}"
                    )

                # Clear the command tag after processing
                await self.set_tag(tag_name, None)

    async def _execute_command(
        self, device: ShellyDevice, component: dict, command: dict
    ):
        """Execute a command against a Shelly device component."""
        action = command.get("action", "")
        comp_type = component["type"]
        comp_id = component["id"]

        if comp_type == "switch":
            if action == "set":
                value = command.get("value", False)
                await self._set_switch(device, comp_id, value)

                # Handle toggle_after (timer)
                toggle_after = command.get("toggle_after")
                if toggle_after and isinstance(toggle_after, (int, float)):
                    asyncio.get_event_loop().call_later(
                        toggle_after,
                        lambda: asyncio.ensure_future(
                            self._toggle_switch(device, comp_id)
                        ),
                    )

            elif action == "toggle":
                await self._toggle_switch(device, comp_id)

        elif comp_type == "cover":
            if action == "open":
                await self._cover_command(device, comp_id, "Open")
            elif action == "close":
                await self._cover_command(device, comp_id, "Close")
            elif action == "stop":
                await self._cover_command(device, comp_id, "Stop")

        elif comp_type == "light":
            if action == "set":
                value = command.get("value", False)
                await self._set_light(device, comp_id, value)
            elif action == "toggle":
                await self._toggle_light(device, comp_id)

    async def _set_switch(self, device: ShellyDevice, comp_id: int, on: bool):
        """Set a switch relay state."""
        if device.generation >= 2:
            on_str = "true" if on else "false"
            await self._http_get(
                device, f"/rpc/Switch.Set?id={comp_id}&on={on_str}"
            )
        else:
            turn = "on" if on else "off"
            await self._http_get(device, f"/relay/{comp_id}?turn={turn}")

    async def _toggle_switch(self, device: ShellyDevice, comp_id: int):
        """Toggle a switch relay."""
        if device.generation >= 2:
            await self._http_get(device, f"/rpc/Switch.Toggle?id={comp_id}")
        else:
            await self._http_get(device, f"/relay/{comp_id}?turn=toggle")

    async def _cover_command(self, device: ShellyDevice, comp_id: int, action: str):
        """Execute a cover command (Gen2+ only)."""
        if device.generation >= 2:
            await self._http_get(device, f"/rpc/Cover.{action}?id={comp_id}")
        else:
            log.warning(
                f"Cover commands not supported for Gen1 device {device.name}"
            )

    async def _set_light(self, device: ShellyDevice, comp_id: int, on: bool):
        """Set a light state."""
        if device.generation >= 2:
            on_str = "true" if on else "false"
            await self._http_get(
                device, f"/rpc/Light.Set?id={comp_id}&on={on_str}"
            )
        else:
            turn = "on" if on else "off"
            await self._http_get(device, f"/light/{comp_id}?turn={turn}")

    async def _toggle_light(self, device: ShellyDevice, comp_id: int):
        """Toggle a light."""
        if device.generation >= 2:
            await self._http_get(device, f"/rpc/Light.Toggle?id={comp_id}")
        else:
            await self._http_get(device, f"/light/{comp_id}?turn=toggle")

    # -------------------------------------------------------------------------
    # Status Polling
    # -------------------------------------------------------------------------

    async def _poll_all_devices(self):
        """Poll all devices for their current status."""
        status_prefix = self.config.status_tag_prefix.value or "status"

        for device in self.devices:
            try:
                if device.generation is None:
                    # Device hasn't been detected yet, try again
                    await self._detect_device(device)
                    if device.generation is None:
                        continue

                if device.generation >= 2:
                    await self._poll_gen2_device(device, status_prefix)
                else:
                    await self._poll_gen1_device(device, status_prefix)

            except Exception as e:
                log.error(f"Error polling device {device.name}: {e}")
                device.consecutive_failures += 1
                device.online = False
                device.last_error = str(e)

                # Set device status to offline
                for component in device.components:
                    tag_name = device.tag_name_for_component(component, status_prefix)
                    await self.set_tag(tag_name, {
                        "online": False,
                        "error": "connection_error",
                        "last_seen": device.last_seen,
                    })

    async def _poll_gen2_device(self, device: ShellyDevice, status_prefix: str):
        """Poll a Gen2+ device for all component statuses."""
        data = await self._http_get(device, "/rpc/Shelly.GetStatus")
        if data is None:
            device.online = False
            device.last_error = "connection_timeout"
            device.consecutive_failures += 1
            return

        device.online = True
        device.last_seen = datetime.now(timezone.utc).isoformat()
        device.last_error = None
        device.consecutive_failures = 0

        for component in device.components:
            comp_type = component["type"]
            comp_id = component["id"]
            key = f"{comp_type}:{comp_id}"
            comp_data = data.get(key, {})

            tag_name = device.tag_name_for_component(component, status_prefix)

            if comp_type == "switch":
                status = {
                    "online": True,
                    "output": comp_data.get("output", False),
                    "apower": comp_data.get("apower"),
                    "voltage": comp_data.get("voltage"),
                    "current": comp_data.get("current"),
                    "temperature_c": (
                        comp_data.get("temperature", {}).get("tC")
                        if isinstance(comp_data.get("temperature"), dict)
                        else None
                    ),
                    "errors": comp_data.get("errors", []),
                    "last_updated": device.last_seen,
                }
            elif comp_type == "input":
                status = {
                    "online": True,
                    "state": comp_data.get("state"),
                    "last_updated": device.last_seen,
                }
            elif comp_type == "cover":
                status = {
                    "online": True,
                    "state": comp_data.get("state"),
                    "current_pos": comp_data.get("current_pos"),
                    "apower": comp_data.get("apower"),
                    "last_updated": device.last_seen,
                }
            elif comp_type == "light":
                status = {
                    "online": True,
                    "output": comp_data.get("output", False),
                    "brightness": comp_data.get("brightness"),
                    "last_updated": device.last_seen,
                }
            else:
                status = {
                    "online": True,
                    "raw": comp_data,
                    "last_updated": device.last_seen,
                }

            await self.set_tag(tag_name, status)

    async def _poll_gen1_device(self, device: ShellyDevice, status_prefix: str):
        """Poll a Gen1 device for all component statuses."""
        for component in device.components:
            comp_type = component["type"]
            comp_id = component["id"]
            tag_name = device.tag_name_for_component(component, status_prefix)

            if comp_type == "switch":
                data = await self._http_get(device, f"/relay/{comp_id}")
                if data is None:
                    device.online = False
                    device.last_error = "connection_timeout"
                    device.consecutive_failures += 1
                    await self.set_tag(tag_name, {
                        "online": False,
                        "error": "connection_timeout",
                        "last_seen": device.last_seen,
                    })
                    return  # Skip remaining components if device is down

                device.online = True
                device.last_seen = datetime.now(timezone.utc).isoformat()
                device.last_error = None
                device.consecutive_failures = 0

                status = {
                    "online": True,
                    "output": data.get("ison", False),
                    "has_timer": data.get("has_timer", False),
                    "timer_remaining": data.get("timer_remaining", 0),
                    "last_updated": device.last_seen,
                }
                await self.set_tag(tag_name, status)

            elif comp_type == "light":
                data = await self._http_get(device, f"/light/{comp_id}")
                if data is None:
                    device.online = False
                    device.last_error = "connection_timeout"
                    device.consecutive_failures += 1
                    await self.set_tag(tag_name, {
                        "online": False,
                        "error": "connection_timeout",
                        "last_seen": device.last_seen,
                    })
                    return

                device.online = True
                device.last_seen = datetime.now(timezone.utc).isoformat()
                device.last_error = None
                device.consecutive_failures = 0

                status = {
                    "online": True,
                    "output": data.get("ison", False),
                    "brightness": data.get("brightness"),
                    "last_updated": device.last_seen,
                }
                await self.set_tag(tag_name, status)

    # -------------------------------------------------------------------------
    # Power Data Publishing
    # -------------------------------------------------------------------------

    async def _publish_power_data_throttled(self):
        """Publish power metrics to data channel, throttled by configured interval."""
        now = time.time()
        interval = self.config.power_publish_interval.value or 60.0

        if now - self.last_power_publish_time < interval:
            return

        power_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "devices": {},
        }

        status_prefix = self.config.status_tag_prefix.value or "status"

        for device in self.devices:
            if not device.online:
                continue

            device_power = {}
            for component in device.components:
                if component["type"] != "switch":
                    continue

                tag_name = device.tag_name_for_component(component, status_prefix)
                status = self.get_tag(tag_name)
                if status and isinstance(status, dict):
                    apower = status.get("apower")
                    voltage = status.get("voltage")
                    current = status.get("current")

                    if apower is not None or voltage is not None:
                        comp_key = f"{component['type']}_{component['id']}"
                        device_power[comp_key] = {
                            "apower": apower,
                            "voltage": voltage,
                            "current": current,
                        }

            if device_power:
                power_data["devices"][device.name] = device_power

        if power_data["devices"]:
            try:
                await self.device_agent.publish_to_channel_async(
                    "power_data", json.dumps(power_data)
                )
                self.last_power_publish_time = now
                log.debug("Published power data to channel")
            except Exception as e:
                log.error(f"Failed to publish power data: {e}")

    # -------------------------------------------------------------------------
    # App Status
    # -------------------------------------------------------------------------

    async def _update_app_status(self):
        """Update the app-level status tag with aggregate device info."""
        devices_online = sum(1 for d in self.devices if d.online)
        devices_total = len(self.devices)

        await self.set_tag("app_status", {
            "state": "running",
            "devices_online": devices_online,
            "devices_total": devices_total,
            "last_poll": datetime.now(timezone.utc).isoformat(),
        })

    # -------------------------------------------------------------------------
    # HTTP Communication
    # -------------------------------------------------------------------------

    async def _http_get(self, device: ShellyDevice, path: str) -> dict | None:
        """Make an HTTP GET request to a Shelly device with retry logic.

        Returns parsed JSON response or None on failure.
        """
        url = f"http://{device.host}{path}"
        max_retries = self.config.retry_count.value or 3

        for attempt in range(max_retries):
            try:
                async with self.session.get(url, auth=device.auth) as resp:
                    if resp.status == 401:
                        log.error(
                            f"Auth failed for {device.name} ({device.host}): "
                            f"HTTP 401"
                        )
                        device.last_error = "auth_failed"
                        device.online = False
                        return None

                    if resp.status != 200:
                        log.warning(
                            f"HTTP {resp.status} from {device.name} "
                            f"({device.host}{path})"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(0.5 * (2 ** attempt))
                            continue
                        return None

                    return await resp.json(content_type=None)

            except asyncio.TimeoutError:
                log.warning(
                    f"Timeout connecting to {device.name} ({device.host}) "
                    f"attempt {attempt + 1}/{max_retries}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))

            except aiohttp.ClientError as e:
                log.warning(
                    f"Connection error for {device.name} ({device.host}): {e} "
                    f"attempt {attempt + 1}/{max_retries}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))

            except Exception as e:
                log.error(
                    f"Unexpected error communicating with {device.name} "
                    f"({device.host}): {e}"
                )
                return None

        return None
