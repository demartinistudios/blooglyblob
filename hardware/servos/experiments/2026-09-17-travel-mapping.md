# Arm travel mapping — observed range accepted for v1

**Session complete:** the user accepted the demonstrated down/forward-raise range and made straight-overhead reach optional. Tests stopped; the original client and output settings were restored after every run. No permanent servo configuration or CAD geometry changed. Pending-observation statements below are a chronological record and are superseded by subsequent observations and the closing decision. The full mechanical span was not measured.

| Physical axis | Pulse, µs | User observation |
| --- | --- | --- |
| Robot-left / photo-right / GPIO12 | 2100 | Perfectly down |
| Robot-left / photo-right / GPIO12 | 2200 | Slightly behind; no need for more backward travel |
| Robot-left / photo-right / GPIO12 | 1000 | Approximately horizontal or slightly above |
| Robot-left / photo-right / GPIO12 | 900 | Light contact with old head |
| Robot-left / photo-right / GPIO12 | 800 | Higher; arm flexed against protruding old head |
| Robot-right / photo-left / GPIO13 | 2000 | Raised well, then confirmed contact with old head; angle unmeasured |
| Robot-right / photo-left / GPIO13 | 900 | User judged down travel sufficient; exact angle unmeasured |

These are observed poses of the existing installed arms, not new runtime settings, strain-free endpoint certifications, or final limits for the redesigned assembly.

The user correctly distinguished direction confirmation from optimal use of travel and requested testing of the full available motion, including backward travel. Earlier recommendations to retain the mirrored CAD placement remain provisional. The electronics task is explicitly holding all measurement questions and hardware access until the complete arm-test sequence is finished.

The robot is assembled. Tests proceed one arm at a time: current configured range first; extensions in increments no greater than 100 µs beyond a physically observed clear interval. No new limit is accepted merely because a command readback succeeds. Supplied-model specification remains 500–2500 µs; that does not establish collision-free travel for the assembled robot. No permanent calibration or code limits have been changed.

## Test 1 — GPIO12, current range

Used [the observed travel probe](arm-travel-probe.py): 2000 → 1500 µs (3-second pause) → 1000 µs (3-second pause) → 2000 µs. Ramps used 10 µs steps every 50 ms. Target duty readbacks were750 and500 at50Hz/range10000. Final readback restored GPIO12/13/16 duties1000/500/750; the same clientPID1019 resumed active. Exit0. Head and other arm were not commanded.

User observation requested: starting, middle and farthest arm poses, plus any contact or strain. **Observation pending.** No extension beyond1000–2000µs has run.

At the user's request, Test1 was repeated unchanged. The repeat also exited0, matched the same target/restoration readbacks and resumed clientPID1019. Physical pose/contact observation is still pending.

## User observation after Test1 repeat

The user reported the farthest position as fully extended, parallel to the floor or slightly higher. On return the arm ended slightly short of hanging perfectly down. The direction of that small resting offset was not explicitly established; no precise angle or center-pause pose was supplied. No contact/strain was reported, but silence alone is not a clearance measurement. This supports an approximately down-to-horizontal current operating sector, not a measured exact90° arc.

Next planned probe: GPIO12 from2000 to2100µs and back, the first100µs extension beyond the existing down-side limit. This will establish whether additional travel takes the arm toward vertical-down or behind the body.

### Physical side identity confirmed

The user identifies the tested GPIO12 arm as the robot's LEFT arm, on the RIGHT side of the supplied front photograph. Use robot-relative left/right in assembly and wiring instructions. Existing CAD construction-script variables call the +X shoulder “right”; with body front−Y and up+Z, +X is viewer-right / robot-left. That historical script naming is not a different physical servo placement. Do not wire by the script variable name: robot-leftGPIO12 corresponds to body+X, robot-rightGPIO13 to body−X in this front-facing convention.

## Test2 — first down-side extension, robot-leftGPIO12

Commanded2000→2100µs, paused3seconds, then returned2000µs. Target duty1050 was read back at50Hz/range10000. Restored all baseline PWM settings and resumed the same active clientPID1019; exit0. No head or robot-right output was written. Physical observation requested before any further extension;2100µs is not yet classified as physically clear.

At the user's explicit request, Test2 was repeated unchanged: robot-leftGPIO12 to2100µs,3-second pause, return2000µs. Target duty1050 and restored baseline duties1000/500/750 were confirmed; exit0, same clientPID1019 resumed. Physical observation is pending; no further travel extension was run.

### Test2 observation

The user reported “Perfectly down” at2100µs for robot-leftGPIO12. This establishes an observed vertical-down reference for this installed arm, without a precision angular measurement. The user did not separately report contact or strain. Next probe extends only100µs to2200, under observation, to establish backward travel.

## Test3 — robot-leftGPIO12 to2200µs

Commanded2000→2200µs, paused3seconds, returned2000µs. Target duty1100 read back correctly; baseline duties1000/500/750 restored at50Hz/range10000, same clientPID1019 resumed active, exit0. Physical observation pending. No further extension is authorized by this readback alone.

### Test3 observation and backward-travel stopping point

The user confirmed2200µs moved the arm slightly behind the body and stated that was fine but there was no need to go that far back. Do not continue toward2500µs on this installed arm.2100µs is the observed straight-down reference and provisional useful lower pose, not a permanently changed software endpoint. We now investigate the forward/upward end, starting with900µs,100µs beyond the existing1000µs up command.

## Test4 — robot-leftGPIO12 to900µs

Commanded2000→900µs, paused3seconds, returned2000µs. Target duty450 read back correctly; all baseline PWM settings restored and same clientPID1019 resumed active, exit0. This is the first100µs upward extension beyond the existing configured interval. User observation pending before any further extension.

### Test4 observation — old head contact, not a new-design limit

At900µs the user confirmed the raised arm touched the old head slightly. The user explicitly said the old body must not serve as the clearance gauge because the new body is substantially redesigned. Agree: this contact is evidence about the old assembly only, not a travel restriction to impose on the new CAD. The test already returned to its original output and resumed the client before the observation arrived.

The agent initially paused further extension and offered physical preparation: either remove the old head/body covering while preserving the installed arm and servo, or remove the arm and use a small supplied horn as a pointer. A replacement pointer changes the angular reference; establish its relationship to the case at a known pulse before transferring angles to the new assembly. This preparation proposal was subsequently superseded by the user clarification below; no parts were removed.

Remaining work: measure the actual unobstructed servo angular span and direction, determine the horn-to-arm installation angle that allocates it to down→forward→up, and check that sector against the new CAD geometry. Keep this distinct from old-prototype collision clearance. No permanent code limits, horn placement or Fusion geometry were changed by these tests. Electronics task remains on hold until the entire arm-test discussion is complete.

### User clarification: keep current assembly for gradual testing

The user declined disassembly, stating “This body is fine. There was nothing that was problematic so far and you showed a good range of motion for the arm.” Treat the previously reported slight touch as accepted by the observing owner, not evidence of binding. Continue the explicitly requested travel mapping in small observed steps on the same assembly; do not impose old-shell contact as a new-CAD limit or claim contact-free movement. Next target800µs,100µs beyond observed900µs.

## Test5 — robot-leftGPIO12 to800µs

Commanded2000→800µs, paused3seconds, returned2000µs. Target duty400 read back correctly; all baseline PWM settings restored, same clientPID1019 resumed active, exit0. User observation pending; no700µs command has been issued.

### Test5 observation and switch to other arm

At800µs the user reported the left arm rose higher but bent slightly against the old head, which protrudes beyond the old body. The user attributes this to the prototype construction and asks how travel compares with the opposite arm. This is actual interference under load; do not extend the left arm further against it. It is not a measured servo endpoint or a limit to transfer to the redesigned geometry. The left arm was already returned to2000µs after the probe.

Next compare robot-rightGPIO13 within its existing1000–2000µs interval:1000→1500→2000→1000, matching the magnitude and pause sequence of robot-left Test1. The reversed pulse direction is expected from the mirrored installation; physical angular equality is not assumed.

## Test6 — robot-rightGPIO13, existing range comparison

Commanded1000→1500µs (3-second pause)→2000µs (3-second pause)→1000µs. Target duties750 and1000 read back correctly. All baseline PWM settings restored; same clientPID1019 resumed active, exit0. Robot-left and head outputs were not written. Physical comparison observation pending; no right-arm extension beyond1000–2000µs has been tested.

### Test6 initial observation

The user said the right-arm motion looked good and it raised “nice and high.” No further movement was commanded. Asked whether the highest pause was horizontal, diagonally upward or nearly overhead, to distinguish an actual difference in mounted angular range from a qualitative impression. Neither matched angular ranges nor unequal horn indexing is established yet.

At the user's request, Test6 was repeated unchanged on robot-rightGPIO13:1000→1500→2000→1000µs,3-second pauses at both targets. Readbacks750/1000 matched, all baseline PWM settings restored, same clientPID1019 resumed active, exit0. Await the user's highest-pose observation before inferring horn alignment or extending travel.

### Test6 repeat observation

The user reported that the robot-right arm touched the old head at its raised position. This does not establish a mechanical servo endpoint or a precise angle. Do not extend its upward travel against that contact. The user next asked how far back/down it can move. Probe robot-rightGPIO13 at900µs,100µs below its current1000µs resting command, under observation.

## Test7 — robot-rightGPIO13 first down/back extension

Commanded1000→900µs, paused3seconds, returned1000µs. Target duty450 matched; all baseline PWM settings restored, same clientPID1019 resumed active, exit0. Physical down/back pose and freedom from contact remain to be reported. No800µs right-arm command has run.

## Closing decision

After Test7, the user said the down travel was sufficient, the overall range was probably good enough, and raising the arms fully vertically could be optional. Stop device tests here; do not run further backward or upward extensions. Keep the present mirrored shoulder arrangement for v1, with down through a forward raise as the accepted motion goal. This is a practical design decision, not proof that the mounting maximizes every possible degree of travel.

Overhead reach has not been disproved: old-head contact interrupted upward tests, the full500–2500µs specified interval was not swept, and the new horn installation angle is not fixed by the old one. The final printed assembly still requires fit, horn alignment and per-axis calibration. Existing CAD down-to-overhead clearance samples remain geometric evidence only, with their previously documented limits. Do not transfer the old collision positions to the new design.

No permanent changes were made to1000–2000µs application limits or servo_calibration.json. Every probe restored baseline GPIO12/13/16 duties1000/500/750 at50Hz/range10000 and resumed the same active clientPID1019. The last probe completed successfully before the acceptance message. The electronics task was explicitly released to resume questions/coordination only after this closing decision.
