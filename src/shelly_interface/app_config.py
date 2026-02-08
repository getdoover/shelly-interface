from pathlib import Path

from pydoover import config


class ShellyInterfaceConfig(config.Schema):
    def __init__(self):
        # Build the component object template
        component = config.Object("Component")
        component.add_elements(
            config.Enum(
                "Type",
                description="Component type",
                choices=["switch", "input", "cover", "light"],
                default="switch",
            ),
            config.Integer(
                "ID",
                description="Component instance ID on the device",
                default=0,
            ),
            config.String(
                "Alias",
                description="Custom alias for this component (used in tag names if set)",
                default="",
            ),
        )

        # Build the device object template
        device = config.Object("Device")
        device.add_elements(
            config.String(
                "Name",
                description="Friendly name for the device (used in tag names)",
            ),
            config.String(
                "Host",
                description="IP address or hostname of the Shelly device",
            ),
            config.String(
                "Auth User",
                description="Username for HTTP auth (if device auth is enabled)",
                default="",
            ),
            config.String(
                "Auth Password",
                description="Password for HTTP auth (if device auth is enabled)",
                default="",
            ),
            config.Array(
                "Components",
                description="Specific components to monitor/control (auto-detected if empty)",
                element=component,
            ),
        )

        # Device list - array of device objects
        self.devices = config.Array(
            "Devices",
            description="List of Shelly devices to manage",
            element=device,
        )

        # Polling and timing settings
        self.poll_interval = config.Number(
            "Poll Interval",
            description="Seconds between polling each device for status updates",
            default=5.0,
        )

        # Tag prefix settings
        self.command_tag_prefix = config.String(
            "Command Tag Prefix",
            description="Prefix for command tags that other apps write to trigger actions",
            default="cmd",
        )
        self.status_tag_prefix = config.String(
            "Status Tag Prefix",
            description="Prefix for status tags published by this app",
            default="status",
        )

        # Power data publishing
        self.publish_power_data = config.Boolean(
            "Publish Power Data",
            description="Whether to publish power metrics to a data channel for logging",
            default=True,
        )
        self.power_publish_interval = config.Number(
            "Power Publish Interval",
            description="Minimum seconds between power data channel publishes",
            default=60.0,
        )

        # Connection settings
        self.connection_timeout = config.Number(
            "Connection Timeout",
            description="HTTP request timeout in seconds per device",
            default=5.0,
        )
        self.retry_count = config.Integer(
            "Retry Count",
            description="Number of retries on failed device communication",
            default=3,
        )

        # Auto-detection
        self.auto_detect_components = config.Boolean(
            "Auto Detect Components",
            description="Auto-detect device components on startup via device info API",
            default=True,
        )


def export():
    ShellyInterfaceConfig().export(
        Path(__file__).parents[2] / "doover_config.json", "shelly_interface"
    )


if __name__ == "__main__":
    export()
