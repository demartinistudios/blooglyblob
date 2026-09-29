# Small arm direction probe — 2026-09-17

The user explicitly authorized a device experiment after confirming the robot was assembled. The purpose was to establish visible direction from the existing resting position, within the existing pulse limits. This was not a full-range sweep or an angle calibration.

## Verified baseline

Read-only SSH confirmed deployed `servo_controller.py` and `servo_calibration.json` match the local 1000–2000 µs configuration and opposite left/right semantic directions. Three initial PWM snapshots were stable; the probe separately required another three seconds of stable resting outputs before pausing the client.

| Existing software axis | GPIO | PWM frequency | Duty / range | Equivalent commanded pulse |
| --- | --- | --- | --- | --- |
| Left arm | 12 | 50 Hz | 1000 / 10000 | 2000 µs |
| Right arm | 13 | 50 Hz | 500 / 10000 | 1000 µs |
| Head | 16 | 50 Hz | 750 / 10000 | 1500 µs |

The live gpiozero outputs use ordinary pigpio PWM. `get_servo_pulsewidth` initially returned “GPIO is not in use for servo pulses”; that was a read-only API mismatch, not evidence that the servo was disconnected. `get_PWM_frequency`, `get_PWM_dutycycle` and `get_PWM_range` established the state above. At 50 Hz, pulse duration is 20,000 µs × duty / range. The underlying PWM real range was 4000, corresponding to 5 µs resolution; no oscilloscope measurement was made.

## Executed sequence and result

Executed [the preserved probe](small-arm-direction-probe.py) through the existing Pi virtual environment, using elevated permission only to pause/resume the root-owned client. The service was active with PID1019 and no systemd watchdog. The probe used SIGSTOP/SIGCONT instead of restarting the application or importing its servo controller, avoiding initialization/cleanup movements. The electronics task agreed not to access hardware during the experiment.

1. Pause client PID1019 and recheck resting outputs.
2. GPIO12: ramp 2000 → 1900 µs in 10 µs steps, hold 1.5 seconds, return to 2000 µs. Repeat once.
3. GPIO13: ramp 1000 → 1100 µs in 10 µs steps, hold 1.5 seconds, return to 1000 µs. Repeat once.
4. Restore original duties, read back all three PWM configurations, and resume the same client.

All four target readbacks matched: GPIO12 duty950 twice, GPIO13 duty550 twice. Restoration readback exactly matched the baseline table for all three pins. The script completed with exit0 and confirmed the service was active with the same PID1019. No head output was written. No firmware, application, calibration, PWM frequency/range or configured endpoint was changed. `finally` restoration and a 25-second interruption timer were included; neither error recovery nor timeout was triggered.

**Physical direction confirmed by the user on a requested repeat.** The first run finished before the user was ready to observe. At their explicit request, the identical probe ran a second time, again completing with exit0, matching all four target readbacks, restoring the baseline and resuming PID1019. The user reported: “Both of them moved towards the front of the body and then back.” Thus decreasing GPIO12 from 2000 to 1900 µs and increasing GPIO13 from 1000 to 1100 µs move the corresponding installed arms forward from their current resting poses. This confirms direction for the current assembly; it does not establish absolute endpoint angles or the new horn indexing. Electrical readback alone does not prove motor movement, angle, torque, absence of binding or correct physical left/right labeling; the forward-motion finding comes from the user’s observation. No angular encoder, camera observation or current measurement was available to this probe. The 100 µs excursion would nominally represent about 9° using the datasheet's linearized range; that is an estimate, not a measurement.

Retain the existing mirrored shoulder case placement while resolving horn installation and actual range. Do not infer full down-to-overhead travel from this test, and do not widen the assembled robot's limits merely because the short command sequence completed.
