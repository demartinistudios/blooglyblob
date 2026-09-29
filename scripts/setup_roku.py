#!/usr/bin/env python3
"""
Roku discovery and configuration script.

Discovers Roku devices on the network and saves the selected device's IP
to the .env file for use by the Blooglyblob application.
"""

from pathlib import Path
import sys

from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .deploy_config import selected_runtime_file, update_env
else:
    try:
        from deploy_config import selected_runtime_file, update_env
    except ModuleNotFoundError:
        from scripts.deploy_config import selected_runtime_file, update_env


def discover_roku_devices(timeout: int = 10) -> list:
    """Discover Roku devices on the local network."""
    try:
        from roku import Roku
    except ImportError:
        print("Error: python-roku library not installed.")
        print("Install it with: make dev-setup (includes python-roku)")
        sys.exit(1)

    print(f"Discovering Roku devices (timeout: {timeout}s)...")
    devices = Roku.discover(timeout=timeout)
    return devices


def get_device_info(device) -> dict:
    """Extract device information."""
    info = device.device_info
    return {
        "name": getattr(info, "user_device_name", None)
        or getattr(info, "model_name", "Unknown"),
        "model": getattr(info, "model_name", "Unknown"),
        "ip": device.host,
    }


def display_devices(devices: list) -> None:
    """Display found devices in a formatted list."""
    print(f"\nFound {len(devices)} Roku device(s):\n")
    for i, device in enumerate(devices, 1):
        info = get_device_info(device)
        print(f"  {i}. {info['name']}")
        print(f"     Model: {info['model']}")
        print(f"     IP: {info['ip']}")
        print()


def select_device(devices: list):
    """Let user select a device, auto-select if only one."""
    if len(devices) == 1:
        info = get_device_info(devices[0])
        print(f"Auto-selecting the only device: {info['name']} ({info['ip']})")
        return devices[0]

    while True:
        try:
            choice = input(f"Select a device (1-{len(devices)}): ").strip()
            index = int(choice) - 1
            if 0 <= index < len(devices):
                return devices[index]
            print(f"Please enter a number between 1 and {len(devices)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)


def update_env_file(env_path: str, roku_ip: str) -> None:
    """Update or create the .env file with ROKU_IP."""
    path = Path(env_path)
    update_env(path, {"ROKU_IP": roku_ip})
    print(f"Updated ROKU_IP in {path}")


def main():
    """Main entry point."""
    env_path = str(selected_runtime_file())

    # Discover devices
    devices = discover_roku_devices(timeout=10)

    if not devices:
        print("No Roku devices found on the network.")
        print("\nTroubleshooting tips:")
        print("  - Make sure your Roku is powered on")
        print("  - Ensure your computer is on the same network as the Roku")
        print("  - Check that network discovery is enabled on your Roku")
        print("    (Settings > System > Advanced system settings > External control)")
        sys.exit(1)

    # Display found devices
    display_devices(devices)

    # Select device
    selected = select_device(devices)
    info = get_device_info(selected)

    # Save to .env
    update_env_file(env_path, info["ip"])

    print("\nRoku configured successfully!")
    print(f"  Device: {info['name']}")
    print(f"  IP: {info['ip']}")


if __name__ == "__main__":
    main()
