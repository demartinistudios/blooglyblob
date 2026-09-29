"""Observed one-arm travel probe; explicit user authorization required each run.

Never launch unattended. Target pulses must lie in the current verified window,
or extend it by at most 100 us. The supplied window is evidence from prior user
observations, not permission inferred from a datasheet. Current defaults are the
unchanged application window. Original arm outputs and client are restored.
"""
import argparse
import json
import os
import signal
import subprocess
import time

import pigpio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pin', type=int, choices=(12, 13), required=True)
    parser.add_argument('--targets-us', type=int, nargs='+', required=True)
    parser.add_argument('--verified-min-us', type=int, default=1000)
    parser.add_argument('--verified-max-us', type=int, default=2000)
    args = parser.parse_args()
    assert 1 <= len(args.targets_us) <= 3
    assert 500 <= args.verified_min_us <= args.verified_max_us <= 2500
    assert all(500 <= value <= 2500 and value % 10 == 0
               and args.verified_min_us - 100 <= value <= args.verified_max_us + 100
               for value in args.targets_us)
    def property_value(name):
        return subprocess.check_output(
            ["systemctl", "show", "blooglyblob", "--value", "--property=" + name],
            text=True,
        ).strip()

    assert os.geteuid() == 0, "Requires permission to pause the root-owned client"
    assert property_value("ActiveState") == "active"
    assert property_value("WatchdogUSec") == "0", "Do not pause a watched client"
    pid = int(property_value("MainPID"))
    assert pid > 1
    with open(f"/proc/{pid}/cmdline", "rb") as stream:
        assert b"pi.main" in stream.read().split(b"\0")
    with open(f"/proc/{pid}/status") as stream:
        assert "\nState:\tT" not in stream.read(), "Already paused by someone else"

    p = pigpio.pi()
    assert p.connected
    baseline = {12: 1000, 13: 500, 16: 750}
    events = []
    paused = False
    touched = set()
    last_duty = dict(baseline)

    def snapshot():
        return {
            pin: {"mode": p.get_mode(pin), "hz": p.get_PWM_frequency(pin),
                  "range": p.get_PWM_range(pin), "duty": p.get_PWM_dutycycle(pin)}
            for pin in baseline
        }

    def assert_rest():
        state = snapshot()
        for pin, duty in baseline.items():
            assert state[pin] == {"mode": 1, "hz": 50, "range": 10000, "duty": duty}, state
        return state

    def interrupted(signum, frame):
        raise RuntimeError(f"Interrupted by signal {signum}; restoring")

    def move(pin, start, end):
        step = 5 if end > start else -5  # 10 us per 50 ms step at this PWM setup
        for duty in range(start + step, end + step, step):
            assert 250 <= duty <= 1250
            touched.add(pin)
            p.set_PWM_dutycycle(pin, duty)
            last_duty[pin] = duty
            time.sleep(0.05)

    try:
        for _ in range(3):
            assert_rest()
            time.sleep(0.5)
        assert int(property_value("MainPID")) == pid
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGALRM):
            signal.signal(sig, interrupted)
        signal.alarm(40)
        os.kill(pid, signal.SIGSTOP)
        paused = True
        time.sleep(0.1)
        assert_rest()
        print(json.dumps({"event": "paused", "pid": pid, "baseline": snapshot()}), flush=True)
        pin = args.pin
        for target_us in args.targets_us:
            target = target_us // 2
            move(pin, last_duty[pin], target)
            readback = p.get_PWM_dutycycle(pin)
            assert abs(readback - target) <= 2
            event = {"pin": pin, "target_us": target_us, "readback_duty": readback}
            events.append(event)
            print(json.dumps(event), flush=True)
            time.sleep(3)
    finally:
        signal.alarm(0)
        try:
            for pin in touched:
                move(pin, last_duty[pin], baseline[pin])
                p.set_PWM_dutycycle(pin, baseline[pin])
            if paused:
                print(json.dumps({"event": "restored_before_resume", "state": snapshot()}), flush=True)
        finally:
            if paused:
                os.kill(pid, signal.SIGCONT)
            p.stop()
    assert int(property_value("MainPID")) == pid
    assert property_value("ActiveState") == "active"
    print(json.dumps({"event": "complete", "client_pid": pid, "client_resumed": True,
                      "motions": events, "angle_measured": False}), flush=True)


if __name__ == "__main__":
    main()
