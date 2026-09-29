#!/usr/bin/env python3
"""
One-time Ring authentication setup script.

Authenticates with Ring API and saves token to .env file.

Usage:
    python scripts/setup_ring.py
"""

import asyncio
import getpass
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .deploy_config import selected_runtime_file, update_env
else:
    try:
        from deploy_config import selected_runtime_file, update_env
    except ModuleNotFoundError:
        from scripts.deploy_config import selected_runtime_file, update_env

from ring_doorbell import Auth, AuthenticationError, Requires2FAError

# Ring API expects Android app user-agent
USER_AGENT = "android:com.ringapp"
ENV_FILE = selected_runtime_file()


def save_token_to_env(token: dict) -> None:
    """Save Ring token to .env file."""
    update_env(ENV_FILE, {"RING_TOKEN": json.dumps(token)})
    print(f"Token saved to {ENV_FILE}")


async def do_auth() -> Auth:
    """Perform interactive authentication with 2FA support."""
    print("Ring Authentication Setup")
    print("=" * 40)
    print()

    username = input("Ring email: ").strip()
    password = getpass.getpass("Ring password: ")

    auth = Auth(USER_AGENT, None, save_token_to_env)

    try:
        await auth.async_fetch_token(username, password)
    except Requires2FAError:
        print()
        print("2FA is enabled on your Ring account.")
        otp_code = input(
            "Enter the 2FA code from your authenticator app or SMS: "
        ).strip()
        await auth.async_fetch_token(username, password, otp_code)

    return auth


async def main() -> int:
    """Main entry point."""
    # Check for existing token
    if ENV_FILE.exists() and "RING_TOKEN=" in ENV_FILE.read_text():
        print("Existing RING_TOKEN found in .env")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 0

    try:
        auth = await do_auth()
        print()
        print("Authentication successful!")
        print(
            "Restart the application after updating its configuration; ordinary updates preserve existing configuration"
        )
        await auth.async_close()
        return 0
    except AuthenticationError as e:
        print(f"Authentication failed: {type(e).__name__}")
        return 1
    except KeyboardInterrupt:
        print("\nAborted.")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
