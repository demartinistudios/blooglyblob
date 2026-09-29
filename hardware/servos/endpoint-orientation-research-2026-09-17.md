# Servo endpoints relative to the case

2026-09-17. User explicitly asked us to find the endpoint orientation for the Kitronik 25105 / FS90MG-CL instead of immediately asking for a physical measurement. This is a source review, not a servo calibration or CAD modification.

## Finding

The exact product documentation specifies electrical neutral, nominal travel and rotation direction, but **no angular datum tying a marked output tooth or an installed horn to a particular case face**. There is no dimensioned drawing establishing that one commanded endpoint points toward the cable end, for example. The attachment angle of the removable horn is part of assembly setup. This is a bounded negative finding from the sources inspected, not proof that no internal factory drawing exists.

## Product-specific evidence

The [Kitronik-linked FS90MG-CL datasheet](https://resources.kitronik.co.uk/pdf/25105-kitronik-clippable-servo-fs90mg-datasheet.pdf), page 2, gives:

| Property | Published value |
| --- | --- |
| Neutral command | 1500 µs |
| Pulse range | 500–2500 µs |
| Nominal running travel | 180° across that range |
| Direction examples | CW from 1500 toward 900 µs; CCW from 1500 toward 2100 µs |

Page 1 lists a 180° mechanical limit and 21-tooth output spline. It does not give tolerance/margin between commanded travel and the physical stops. The direction table does not explicitly label a viewing direction, so it is insufficient by itself to assign robot-left/robot-right commands.

The [25105 technical drawing](https://resources.kitronik.co.uk/pdf/25105-kitronik-clippable-servo-technical-drawing.pdf) gives case dimensions, shaft location and 21T spline designation. Visual inspection found no zero mark, designated tooth, angular tolerance or endpoint orientation. Both official PDFs were read from their previously saved local copies and rechecked against the product page's current links. Their complete pages were visually inspected for angular annotations.

[Kitronik's product page](https://kitronik.co.uk/products/25105-clippable-servo) describes approximately 180° total, approximately 90° each way, with four supplied horns. This is nominal capability, not a guarantee of exact symmetric travel on each unit.

## Why horn installation matters

[Adafruit's servo assembly guide](https://learn.adafruit.com/experimenters-guide-for-metro/proj08-assembly) centers the servo electrically before removing and reinstalling the horn at the desired orientation. [Kitronik's own robotics example](https://kitronik.co.uk/blogs/resources/add-servo-simple-robotics-kit) also determines useful up/down commands experimentally for its chosen horn installation. That example uses a different servo and establishes the assembly principle only; its numerical positions must not be used for this robot.

[Pololu's detailed servo-interface explanation](https://www.pololu.com/blog/17/servo-control-interface-in-detail) distinguishes nominal neutral from the middle of the actual available travel and explains why individual calibration is needed to maximize usable range. It is supporting general guidance, not a replacement for the FS90MG-CL specification.

With a 21-tooth spline, one tooth corresponds to **360/21 ≈ 17.14°**. This is a geometric calculation, not a measured alignment error. Choosing the nearest tooth alone can leave up to approximately 8.57° of nominal alignment error for a fixed horn orientation. Other available horn-hole orientations may improve this, but the measured disk-hole pattern has not been angularly mapped, so no improvement is assumed. The existing adapter's radial slots accommodate spacing variation; they are not a designed continuous angular adjustment.

## Consequence for this design

The desired arm motion remains down → forward-horizontal → overhead. A centered servo with the assembled arm placed approximately forward-horizontal is the starting installation plan; the mirrored shoulder installations require separate direction checks. The dome's centered installation should face forward. These are intended assembly datums, not published factory shaft angles.

CAD has checked the specified geometric sectors, including the latest arms, but has not established pulse-to-pose mapping, spline indexing offsets or an exact full down-to-overhead operating range. For a kit, record each servo's neutral/direction/endpoints and make the horn installation orientation explicit. If exact poses and maximal travel cannot coexist after indexing, adjust the mechanical horn-to-part clocking rather than assuming software trim creates more mechanical travel. No clocking adjustment has been added yet.

The local code still sets 1000–2000 µs in `pi/servo_controller.py:33–34` and `pi/calibrate_servos.py:41–42`, narrower than the published full-range interval. Nominal linear scaling would suggest about 90° across that interval, but actual travel is unmeasured. This can contribute to restricted motion independently of the mount orientation. No pulse limits were widened.

Next evidence is a controlled unloaded calibration on the actual units, or a manufacturer-supplied neutral-to-case/spline datum with tolerance. No manufacturer contact, physical servo command, motor disassembly, forced stop test or Fusion change was performed for this research.

## Original mounting compared with the live CAD

The user reported that one shoulder servo label faces forward and the other backward; this kept the two shafts at equal height on the wooden post. The robot is now assembled, so that observation does not authorize an unloaded-motion assumption. No physical movement was commanded during this review.

Read-only inspection of the actual Fusion v3 occurrences confirmed the construction-script placement, rather than relying only on the illustration:

| Reference | Origin in body coordinates, mm | Output direction | Case local long-axis direction |
| --- | --- | --- | --- |
| CAD right shoulder | (10.3, 0, 90) | +X | +Z |
| CAD left shoulder | (−10.3, 0, 90) | −X | +Z |
| Head | (0, 0, 86.6) | +Z | +Y |

Body front is −Y. The two shoulder transforms differ by a proper 180° rotation around body Z, not a reflected physical servo. Both modeled cases extend from Z73.6 to Z96.1 along their long dimension, with output centers at Z90. Both shafts point laterally outward; the heavier case portion lies below the output center. Both mounting-hole pairs therefore occupy the same heights. The simplified references omit stickers and detailed cable exits; the exact label face cannot be read from these CAD bodies. Opposite sticker directions on otherwise identical real units are consistent with this arrangement.

Recommendation: retain the current mirrored shoulder arrangement and removable P03 carrier. It provides equal shoulder height, cases below the head mechanism, outward horn/screw access and separate servo removal. There is no evidence that matching the sticker directions would improve travel. Turning a case about its own output axis changes packaging and the arm's offset relative to the case; it does not increase the servo's internal travel. Pointing two output axes in opposite world directions reverses the apparent world rotation for an equal local shaft rotation. The opposite software directions are consistent with that geometry, but labels alone do not prove direction or endpoint angles.

## Software mapping review

Local `pi/servo_controller.py` and `pi/calibrate_servos.py` use 1000–2000 µs. `pi/servo_config.py` loads `pi/servo_calibration.json`; the existing semantic commands resolve as follows:

| Axis (existing software names) | Command A | Neutral | Command B |
| --- | --- | --- | --- |
| Left arm, GPIO12 | Down: +1 / 2000 µs | 0 / 1500 µs | Up: −1 / 1000 µs |
| Right arm, GPIO13 | Down: −1 / 1000 µs | 0 / 1500 µs | Up: +1 / 2000 µs |
| Head, GPIO16 | Left: +1 / 2000 µs | Center: 0 / 1500 µs | Right: −1 / 1000 µs |

Pulse conversion follows the [gpiozero Servo implementation](https://gpiozero.readthedocs.io/en/stable/_modules/gpiozero/output_devices.html#Servo): 1500 + 500 × normalized value for these configured bounds. These semantic names and stored positions are commands, not angle feedback. The local labels “up” and “down” do not establish whether the old arm travels 90°, 180°, or another measured amount. Likewise, the actual CAD arms-down display is a geometric reference pose, not a claim that 1500 µs produces arms down. The proposed new assembly datum is arms forward-horizontal at neutral, placing the intended down-to-overhead sector around neutral.

Inspection also found that constructing gpiozero Servo without `initial_value=None` commands its midpoint; `ServoController` subsequently calls `rest()`. The interactive calibration tool initializes servos and centers during cleanup. Therefore neither program was launched as a read-only diagnostic. No PWM limits or calibration values were edited.

Next physical evidence should use a single unloaded servo with a visible pointer, known case direction and known commands, recording actual angle rather than inferring it from the round shaft. Center first, establish direction with small increments, then characterize usable travel incrementally within the exact model's specified interval without driving against a stop. Install each new arm near forward-horizontal at calibrated neutral, account for spline indexing, then verify clearance and establish conservative loaded limits. The dome should face forward at its calibrated center, with its own cable-limited travel. No exact 180° usable loaded range is promised. Mechanical packaging can retain this orientation while calibration remains a separate fit-validation step.

### Deployed configuration confirmed

Read-only SSH on 2026-09-17 confirmed `/home/pi/blooglyblob/pi/servo_calibration.json` matches the local table above, and the deployed `servo_controller.py` also sets 1000–2000 µs. The hardware service was active (PID1019). No code was imported and no servo was commanded for this check. Earlier SSH attempts failed before authentication; direct credential parsing with the existing repo configuration succeeded. The user subsequently authorized a device experiment; the baseline preservation commit precedes that experiment.

### Small authorized device experiment

After the baseline commit, the user authorized an assembled-device experiment. A 100 µs inward excursion and return was commanded twice on each arm, with exclusive control, unchanged head output and verified restoration of the original client/PWM state. The user requested a repeat and confirmed that both arms moved toward the front and returned. This validates the current assembly’s direction mapping; usable angles and the new assembly’s horn indexing remain unmeasured. This supersedes earlier “no physical commands” statements only for this later experiment; no endpoint expansion was made. See [protocol, command readbacks and limits](experiments/2026-09-17-direction-probe.md).

### Full-travel question reopened; old-body contact isolated

The user correctly noted that the small direction test did not establish optimal mounting or allocation of full travel. Further observed tests found the current robot-left arm (GPIO12, viewer-right, CAD body+X) approximately horizontal at1000µs, perfectly down at2100µs, and slightly behind at2200µs. At900µs it touched the old head slightly. The user does not want old-body clearance to constrain the redesign. All test commands returned to their original outputs and the same client resumed; permanent settings were not edited. The agent proposed clearing the old parts, but the observing user clarified that the light contact was not problematic and requested no disassembly. Gradual observed travel testing continues on the existing assembly; old-shell contact remains distinct from redesigned clearance. See [the in-progress travel map](experiments/2026-09-17-travel-mapping.md). Earlier recommendations to retain the mounting are provisional until travel allocation and new-CAD clearance are assessed separately.

### V1 decision after observed tests

The user accepted the demonstrated down/forward-raise motion and made fully vertical overhead reach optional. All arm tests have stopped; original outputs and client were restored, with no permanent configuration change. The new design retains its mirrored shoulder mounting provisionally. Full mechanical range, exact old-arm angles and new horn indexing remain unmeasured; old-head contact is not a limit for the redesigned CAD. Final observations and scope are in [the completed session record](experiments/2026-09-17-travel-mapping.md).
