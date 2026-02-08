"""
Basic tests for an application.

This ensures all modules are importable and that the config is valid.
"""

def test_import_app():
    from shelly_interface.application import ShellyInterfaceApplication
    assert ShellyInterfaceApplication

def test_config():
    from shelly_interface.app_config import ShellyInterfaceConfig

    config = ShellyInterfaceConfig()
    assert isinstance(config.to_dict(), dict)

def test_ui():
    from shelly_interface.app_ui import ShellyInterfaceUI
    assert ShellyInterfaceUI

def test_state():
    from shelly_interface.app_state import ShellyInterfaceState
    assert ShellyInterfaceState