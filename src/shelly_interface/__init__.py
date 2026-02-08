from pydoover.docker import run_app

from .application import ShellyInterfaceApplication
from .app_config import ShellyInterfaceConfig

def main():
    """
    Run the application.
    """
    run_app(ShellyInterfaceApplication(config=ShellyInterfaceConfig()))
