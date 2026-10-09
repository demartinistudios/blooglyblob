# BlooglyBlob servo fit reference

This page backs up two build guide steps: "Hold the fit position" and "Attach the head shelf and arms". It lists the values the fit command uses and what to do if a part does not line up.

## The fit position

The fit position is the servo position set by `make pi-servo-fit`: head facing forward, arms hanging straight down. The application also moves the servos here when it starts.

| Servo | Pi GPIO (BCM) | Pi header pin | Signal wire | Fit pulse | Part position |
| --- | --- | --- | --- | --- | --- |
| Robot-left arm | 12 | 32 | S1 C5, labeled LEFT | 2000 µs | Hanging straight down |
| Robot-right arm | 13 | 33 | S2 D5, labeled RIGHT | 1000 µs | Hanging straight down |
| Head | 16 | 36 | S2 C5, labeled HEAD | 1500 µs | Facing forward |

Robot-left is the robot's own left: on your right when you face it.

The two arm pulses differ because the shoulder servos face opposite ways. The same arm position is at opposite ends of their travel.

## Hold the fit position

1. Start with the head shelf, head and both upper arms off the servo shafts. In the build, the robot stands on its feet, powered, after the light test. The head light cable runs up through a gap in the loose head shelf.
2. On your computer, in the `blooglyblob` folder, run:

   ```sh
   make pi-servo-fit
   ```

   It stops the robot application and holds all three servos at the fit position. Leave it waiting.

## Fit the parts while the servos hold

- **Head shelf:** turn the head shelf (P08) so its side with no nut pocket faces front. Set its horn on the head servo shaft, with the shelf front nearest straight ahead. Turn the shelf, not the shaft, to mesh them. Press it down.
- **Arms:** at the robot-left shoulder, on your right as you face the robot, set the robot-left upper arm (AR01) on its shaft, hanging nearest straight down. Turn the arm, not the shaft, to mesh them. Press it on. Seat the robot-right upper arm (AR04) the same way.
- If a horn does not slide on, lift it off, turn it one tooth and try again. Do not force it.

The spline has 21 teeth, about 17° apart. A part can sit up to half a tooth (about 8°) from the fit position. That is normal. Choose the nearest tooth. Do not force a horn or bend an arm to make up the difference.

## Release, shut down and fasten

1. At the waiting command, type `STOP` and press Enter. The output says the servo pulses stopped and the application stays stopped. If it says the servo output release is unconfirmed, unplug the supply from the wall at once.
2. Shut the Pi down:

   ```sh
   make pi-ssh
   sudo poweroff
   ```

3. Wait 30 seconds after SSH disconnects. Unplug the supply from the wall. Unplugging is the only power cutoff for the servos; there is no separate servo switch.
4. Hold the shelf still and drive the horn's own center screw. Do not use an M2 screw. Hold each upper arm still and drive its horn's center screw through the arm's outer face. Do not use a center screw to pull a horn onto the spline.

Unpowered shafts are not held in place. If a part turned while you fastened it, take it off and fit it again as above.

## After fitting

In the guide's "Check the first movement" step, the robot stands on its feet with the bottom cover off. When you plug the supply back in, the application starts by itself and moves each servo to the fit position. The head and arms may shift a little.

## Movement limits

The limits are built into the software. There is no calibration file to adjust, but every replacement servo still needs the fitting and first-movement checks above. All three outputs use 50 Hz (a 20 ms frame).

| Servo | Pulse range | What that means |
| --- | --- | --- |
| Robot-left arm | 1000–2000 µs | From hanging down (2000) up to about level in front |
| Robot-right arm | 1000–2000 µs | From hanging down (1000) up to about level in front |
| Head | 1000–2000 µs | About 45° each way from forward (1500) |

## If something is wrong

| What you see | What to do |
| --- | --- |
| `make pi-servo-fit` cannot reach the Pi | Check that the robot is plugged in and has had a minute to start, and that `make pi-check` works. |
| A shaft does not move, or buzzes and strains | Unplug the supply. Check that servo's three connections (+, − and signal) against the table above and the wiring step. |
| An arm or the head is a tooth off after fitting | Unplug, remove the center screw and lift the part off. Fit it again while the servos hold, as above. Do not turn the servo shaft by hand. |
| A part touches the body during the first-movement check | Unplug at once. Take that part off and fit it again while the servos hold, as above. |

A jammed servo can keep pushing and overheat. Unplug the supply immediately if an arm or the head strains.

BlooglyBlob: <https://github.com/demartinistudios/blooglyblob>
