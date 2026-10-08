"""Hold the assembly fit pose; invoke through make pi-servo-fit."""

import argparse
import signal

# Shared exit contract with the application and stdlib-only installer. Avoid
# importing the full application and its audio/model dependencies for fitting.
OWNERSHIP_UNCERTAIN_EXIT = 73


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    # Load configuration before importing any hardware settings. Importing this
    # module alone remains safe on a computer without GPIO drivers.
    from blooglyblob.config import load_runtime_environment

    load_runtime_environment()
    from blooglyblob.hardware import servo_controller
    from blooglyblob.hardware.local_media import HardwareReleaseError

    if not servo_controller.ON_PI:
        print("Servo fitting requires the Pi GPIO drivers; no simulation was run.")
        return 1

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    handlers = {
        sig: signal.signal(sig, interrupted)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    controller = None
    result = 0
    try:
        controller = servo_controller.ServoController()
        print(
            "Holding the fit pose. Seat the head shelf and arms now without turning the shafts."
        )
        while (
            input("Type STOP then Enter to release the servos: ").strip().upper()
            != "STOP"
        ):
            pass
    except (EOFError, KeyboardInterrupt):
        print("Servo fitting interrupted.")
        result = 1
    except HardwareReleaseError:
        result = OWNERSHIP_UNCERTAIN_EXIT
    except Exception:
        print("Servo fitting failed; inspect the outputs before continuing.")
        result = 1
    finally:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if controller is not None:
                try:
                    controller.cleanup()
                except Exception:
                    result = OWNERSHIP_UNCERTAIN_EXIT
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    if result == OWNERSHIP_UNCERTAIN_EXIT:
        print("Servo output release is unconfirmed. Switch off the supply.")
    elif result:
        print("Servo pulses stopped. The application stays stopped.")
    else:
        print(
            "Servo pulses stopped. The application stays stopped. "
            "Shut down and unplug, then drive the center screws."
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
