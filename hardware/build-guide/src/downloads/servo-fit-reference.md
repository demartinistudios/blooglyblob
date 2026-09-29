# BlooglyBlob servo fit reference

This page backs up the build guide's "Set the fit pose and attach the head and arms" step. It lists the values the fit command uses and what to do if something doesn't line up.

## What the fit pose is

First move all three servos to a known position, the **fit pose**. Then stop the command, shut down and unplug before attaching the head and arms. Avoid turning the shafts while fitting:

| Servo | Pi GPIO (BCM) | Pi header pin | Signal wire | Fit pulse | Part position |
| --- | --- | --- | --- | --- | --- |
| Robot-left arm | 12 | 32 | S1 C5, labeled LEFT | 2000 µs | Hanging straight down |
| Robot-right arm | 13 | 33 | S2 D5, labeled RIGHT | 1000 µs | Hanging straight down |
| Head | 16 | 36 | S2 C5, labeled HEAD | 1500 µs | Facing forward |

Robot-left is the robot's own left: on your right when you face it.

The two arm pulses are different because the shoulder servos face opposite ways: the same arm position is at opposite ends of their travel.

## Run the fit command

1. Stand the robot upright with room around it and the bottom cover off. Leave the head, head shelf and arms **off** the servo shafts.
2. Plug in the supply and wait about a minute for the Pi to start.
3. On your computer, in the `blooglyblob` folder:

   ```sh
   make pi-servo-fit
   ```

   It stops the robot application, then turns all three servos to the fit pose and holds them there.
4. When the shafts have stopped moving, type `STOP` and press Enter. The servos stop holding, the application stays stopped, and the shafts are no longer held. Avoid turning them before fitting.
5. Shut the Pi down and unplug the supply:

   ```sh
   make pi-ssh
   sudo poweroff
   ```

   Wait until the Pi's green light stops flashing, then unplug the supply from the robot. Unplugging is the power cutoff for the servos; there is no separate servo switch.

Don't turn the bare shafts by hand after this.

## Fit the parts

- **Head:** push the head shelf's horn onto the head-servo shaft with the shelf facing the robot's front, on the nearest spline tooth. Fit the servo's center screw.
- **Arms:** push each upper arm's horn onto its shoulder shaft with the arm hanging straight down beside the body, on the nearest tooth. AR01 goes on the robot's left, AR04 on the right. Fit each center screw.
- Never use a center screw to pull a horn onto the spline. If it doesn't slide on, lift it off, turn it one tooth and try again.

The spline has 21 teeth, so each tooth is about 17°. A part can end up as much as half a tooth (about 8°) away from the ideal pose. That's normal: choose the closest tooth, and don't force a horn or bend an arm to make up the difference.

## After fitting

Plug the supply back in. The application starts by itself and moves each servo straight to its rest pose: head forward, arms hanging down. Because that's the pose you fitted them in, expect little or no movement. Then do the first-movement check in the guide.

## Movement limits

The limits are built into the software. There is no calibration file to adjust, but every replacement servo still needs the fitting and first-movement checks above. All three outputs use 50 Hz (a 20 ms frame).

| Servo | Pulse range | What that means |
| --- | --- | --- |
| Robot-left arm | 1000–2000 µs | From hanging down (2000) up to about level in front |
| Robot-right arm | 1000–2000 µs | From hanging down (1000) up to about level in front |
| Head | 1000–2000 µs | About 45° each way from forward (1500) |

The Kitronik FS90MG-CL (Kitronik 25105) datasheet specifies nominal 180° travel
across 500–2500 µs, 1500 µs center, and an 8 µs dead band. The narrower operating
window above spans roughly 90° nominally. The datasheet does not specify endpoint
tolerance, a guaranteed margin to mechanical stops, or exact installed angles.
The 8 µs dead band is not a safety margin. Keep the fixed limits until clearance
has been checked on the new assembly; do not widen them from the datasheet alone.
Older calibration files are ignored, so previously calibrated builds must be
refitted for these positions before operation.

## If something is wrong

| What you see | What to do |
| --- | --- |
| `make pi-servo-fit` can't reach the Pi | Check that the robot is plugged in and has had a minute to start, and that `make pi-check` works. |
| A shaft doesn't move, or buzzes and strains | Unplug the supply. Check that servo's three connections (+, − and signal) against the table above and the wiring step. |
| An arm or the head is a tooth off after fitting | Unplug, remove the center screw, lift the horn off, turn it one tooth and refit it. Don't turn the servo shaft by hand. |
| A part touches the body during the first-movement check | Unplug at once and refit that part one tooth closer to its pose. |

A servo with a jammed arm or head isn't protected by the fuses, so never leave one straining.

BlooglyBlob: <https://github.com/demartinistudios/blooglyblob>
