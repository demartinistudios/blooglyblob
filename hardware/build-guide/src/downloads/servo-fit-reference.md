# BlooglyBlob servo fit reference

This page backs up two build guide steps: "Set the fit position" and "Attach the head shelf and arms". It lists the values the fit command uses and what to do if a part does not line up.

## The fit position

The fit position is the servo position set by `make pi-servo-fit`: head facing forward, arms hanging straight down. The application also moves the servos here when it starts.

| Servo | Pi GPIO (BCM) | Pi header pin | Signal wire | Fit pulse | Part position |
| --- | --- | --- | --- | --- | --- |
| Robot-left arm | 12 | 32 | S1 C5, labeled LEFT | 2000 µs | Hanging straight down |
| Robot-right arm | 13 | 33 | S2 D5, labeled RIGHT | 1000 µs | Hanging straight down |
| Head | 16 | 36 | S2 C5, labeled HEAD | 1500 µs | Facing forward |

Robot-left is the robot's own left: on your right when you face it.

The two arm pulses differ because the shoulder servos face opposite ways. The same arm position is at opposite ends of their travel.

## Set the fit position

1. Start with the head shelf, head and both upper arms off the servo shafts. In the build, the robot still lies on its back on folded towels from the light test, powered, with the power jack (J1) hanging clear.
2. On your computer, in the `blooglyblob` folder, run:

   ```sh
   make pi-servo-fit
   ```

   It stops the robot application and holds all three servos at the fit position. The shafts barely move, because the application set this position at startup.
3. When the output asks, type `STOP` and press Enter. The output says the servo pulses stopped and the application stays stopped. If it says the servo output release is unconfirmed, unplug the supply from the wall at once.
4. Shut the Pi down:

   ```sh
   make pi-ssh
   sudo poweroff
   ```

5. Through the open bottom, wait for the Pi's green activity light to stop flashing. Unplug the supply from the wall. Unplug the barrel plug from J1. Unplugging is the only power cutoff for the servos; there is no separate servo switch.

Do not turn the three servo shafts by hand after this. Unpowered shafts are not held in place.

## Fit the parts

Stand the robot on its feet on a folded towel, with one hand under the base and one under the backpack. Keep your hands off the three servo shafts.

- **Head shelf:** turn the head shelf (P08) so its side with no nut pocket faces front. Set its horn on the head servo shaft, with the shelf front nearest straight ahead. Turn the shelf, not the shaft, to mesh them. Press it down. Drive the horn's own center screw. Do not use an M2 screw.
- **Arms:** at the robot-left shoulder, on your right as you face the robot, set the robot-left upper arm (AR01) on its shaft, hanging nearest straight down. Turn the arm, not the shaft, to mesh them. Press it on. Drive its horn's center screw through the upper arm's outer face. Fit the robot-right upper arm (AR04) the same way.
- Do not use a center screw to pull a horn onto the spline. If a horn does not slide on, lift it off, turn it one tooth and try again.

The spline has 21 teeth, about 17° apart. A part can sit up to half a tooth (about 8°) from the fit position. That is normal. Choose the nearest tooth. Do not force a horn or bend an arm to make up the difference.

## After fitting

In the guide's "Check the first movement" step, the robot stands on its feet with the bottom cover off. When you plug the supply back in, the application starts by itself and moves each servo straight to the fit position. The head and arms barely move, because you fitted them there.

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
| `make pi-servo-fit` cannot reach the Pi | Check that the robot is plugged in and has had a minute to start, and that `make pi-check` works. |
| A shaft does not move, or buzzes and strains | Unplug the supply. Check that servo's three connections (+, − and signal) against the table above and the wiring step. |
| An arm or the head is a tooth off after fitting | Unplug, remove the center screw, lift the horn off, turn it one tooth and refit it. Do not turn the servo shaft by hand. |
| A part touches the body during the first-movement check | Unplug at once. Refit that part one tooth closer to the fit position. |

A servo with a jammed arm or head is not protected by the fuses, so never leave one straining.

BlooglyBlob: <https://github.com/demartinistudios/blooglyblob>
