"""Foreground and systemd use the same configuration and process deadline."""

import asyncio
import logging
import os
import threading

from blooglyblob.config import load_ai_config, load_runtime_environment


def run_application(application, *, shutdown_seconds=15.0):
    """The final watchdog includes asyncio teardown and Python executor threads.

    os._exit is deliberately restricted to this process entry boundary, never
    controller tests or an embedding application's loop.
    """
    from blooglyblob.application import OWNERSHIP_UNCERTAIN_EXIT, OwnershipUncertain

    watchdog = None

    def expire():
        os.write(2, b"Application shutdown ownership unconfirmed; terminating\n")
        os._exit(OWNERSHIP_UNCERTAIN_EXIT)

    def arm():
        nonlocal watchdog
        if watchdog is None:
            watchdog = threading.Timer(shutdown_seconds, expire)
            watchdog.daemon = True
            watchdog.start()

    application._on_shutdown = arm
    try:
        asyncio.run(application.run_forever())
    except OwnershipUncertain:
        expire()
    except KeyboardInterrupt:
        arm()
    finally:
        # Successful asyncio teardown is not enough if a custom executor remains.
        # The application reports those as OwnershipUncertain before this point.
        if watchdog:
            watchdog.cancel()


def main():
    load_runtime_environment()
    config = load_ai_config()
    # Hardware consumers are imported only after the selected environment loads.
    from blooglyblob.application import Application, SHUTDOWN_SECONDS

    run_application(Application(config=config), shutdown_seconds=SHUTDOWN_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    try:
        main()
    except Exception as error:
        logging.getLogger(__name__).error(
            "Application stopped (%s)", type(error).__name__
        )
        raise SystemExit(1) from None
