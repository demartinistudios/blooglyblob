"""One-off, explicitly authorized assembled-robot direction probe.

Run on the Pi as root only while its owner is observing. Requires the exact
known resting PWM setup; aborts on other states. Does not import robot code.
Temporarily pauses the existing client, preserves PWM mode/frequency/range,
moves each arm inward by 100 us, restores duties, and resumes the same client.
Readbacks establish commanded pulses only, never measured shaft angles.
"""
import json
import os
import signal
import subprocess
import time

import pigpio


def main():
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
            assert 500 <= duty <= 1000
            touched.add(pin)
            p.set_PWM_dutycycle(pin, duty)
            time.sleep(0.05)

    try:
        for _ in range(6):
            assert_rest()
            time.sleep(0.5)
        assert int(property_value("MainPID")) == pid
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGALRM):
            signal.signal(sig, interrupted)
        signal.alarm(25)
        os.kill(pid, signal.SIGSTOP)
        paused = True
        time.sleep(0.1)
        assert_rest()
        print(json.dumps({"event": "paused", "pid": pid, "baseline": snapshot()}), flush=True)
        for pin, target in ((12, 950), (13, 550)):
            for cycle in (1, 2):
                move(pin, baseline[pin], target)
                readback = p.get_PWM_dutycycle(pin)
                assert abs(readback - target) <= 2
                event = {"pin": pin, "cycle": cycle, "target_us": target * 2,
                         "readback_duty": readback}
                events.append(event)
                print(json.dumps(event), flush=True)
                time.sleep(1.5)
                move(pin, target, baseline[pin])
                time.sleep(0.5)
            time.sleep(1)
    finally:
        signal.alarm(0)
        try:
            for pin in touched:
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
