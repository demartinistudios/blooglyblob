# Current hardware notes

For agents: design constraints, rationale and evidence.
Builders should follow the [illustrated guide](https://demartinistudios.github.io/blooglyblob/).

The registry selects R34, Fusion cloud version 32. The native assembly, STL
exports and print projects are the maintained build inputs. Historical revision
names in current evidence identify the source of unchanged features.

## Portable assembly

Download the [Fusion assembly (.f3d)](current/assembly.f3d) or the
[STEP AP214 assembly (.step)](current/assembly.step). The STEP exports the full
R34/cloud32 assembly, including hidden reference, layout and test components.
Reimport into Fusion retained all 563 bodies and 331 occurrences in their assembly
positions. It contains geometry and component placements, without Fusion
parametric history or joints. Body names and occurrence suffixes may change on import.
[Export provenance](current/step-export-provenance.json) records the source,
hash and measured reimport checks.

## Mouth and upper bearing collar

R34 replaces the mouth with the matching P31 eight-channel holder and P30 rear
cover. Fit the 4 mm LD45 strip trimmed to 5.75 mm high, seat the board in the
cover pocket with LEDs forward, and route its leads through the open notch.
Two M2×8 screws enter from the rear into the retained head nuts. There are no
separate PCB screws or washers. The head shell and head adapters are unchanged.

P44 is the upper copper bearing collar; P01 is now the unchanged lower collar
only. P44 has an 11.2 mm overall height and bearing surface at Z120.5 mm. The
original two M3×10 screws remain seated at Z116.3 mm below the bearing face.
Clear the two 0.20 mm sacrificial screw-bore films after printing. The C01 clear
bearing film is nominally 0.17 mm thick, with two 3.2 mm inward tabs folded down
2.5 mm into the locating slots. Its outer diameter is 82.6 mm and inner circle
is 62 mm. Secure the servo horn normally and check free head rotation.

The [release evidence](current/evidence/mouth-collar-r34.json) and
[STL frames](current/frames/mouth-collar-r34.json) bind these parts to the saved
native assembly. All unrelated geometry and original part colors are retained.

## Body lighting and head carrier

R33 uses five changed pieces: P43 front upright, P04 head-servo carrier,
P11 lower light bracket, P42 upper light bracket and P12 rear-mounted middle
light bracket. P02 is now the unchanged rear upright only. The P13 wire guide
is retired. There are 70 required printed pieces across 53 types, plus one
optional print instance. P10 seam covers, base and shoulder carrier are unchanged.

P43 has a deeper front chamfer, local fastening lands and an inset P04 mounting
seat. Its opposite M3 nut recess is fully recessed relative to the post's flat
side; the chamfer exposes part of the perimeter. The guide uses an iexcell M3×14
button-head screw for this sideways front carrier connection, following the
owner-built configuration. Its head remains raised above the recess. The rear
carrier connection retains an M3×20 socket-head screw from the Kadrick M3 kit.

P04 thickens the front servo-ear crossbar to 5.3 mm with a shallow 1.8 mm nut
recess and 3.5 mm of solid bearing above it. Both servo screw heads face upward:
front M2×8 and rear M2×6, with ordinary M2 nuts below. The servo shaft points up
at the rear end of its body, away from the front post. Assemble the servo and
carrier on the bench while the underside nuts are accessible.

P11 and P42 mount behind the front upright using two iexcell M3×14 button-head
screws and two M3 nuts. The owner confirmed the button heads and tip clearance
in the assembled front post. Install the upper light bracket before the servo
carriers block access. P12 retains the rear mounting and brings its LEDs forward to the middle
height. Retain six Pebbles and two ties per Pebble. The lower and middle pad ends
have a 6 mm gap. Route every wire behind its pad after clearing the end ties,
never across a light’s face. The lower top and middle bottom wires cross behind
the front upright. Keep slack clear of servos and screw access. The local modeled
envelope is 5×0.95 mm with a 5 mm bend radius; complete strand slack was not simulated.

[Native and interface evidence](current/evidence/body-lighting-r33.json) records
geometry and clearance checks. The accepted trial improved assembly and lighting;
it is not a quantified strength or optical qualification. The inherited carrier
tab edge has only 0.2 mm modeled upper-bracket clearance, while added reinforcement
clears its adjacent bracket root by 1 mm. Check printed parts before tightening.

The build guide provides the assembly order, illustrations, hardware lists and
supply cards. Its [review summary](../build-guide/REVIEW.md) records the scope of
the source and visual checks.

## Body foam reference

C04 is a display-only 4 mm shell, with radii 34.1–38.1 mm and height 114.3 mm.
Two round Ø14 mm holes lie on the shoulder X axis at Z = 90 mm. The rear (+Y)
seam has a continuous 2 mm gap, without windows, knife slits or edge notches.
Backing ribs remain unchanged; the foam edges compress against them.
[Native verification](current/evidence/body-foam-r32.json) and
[print reuse](../printing/current/checks/r32-print-reuse.json) record this reference-only update.
Guide images showing the foam use the selected rendering inputs.

## Electrical references

The assembly contains one lighting fuse holder, F2, in its accepted location.
The F2 placement and all eight arm joints remain unchanged by R33. See [native verification](current/evidence/fuse-reference-r31.json)
and [print reuse evidence](../printing/current/checks/r31-print-reuse.json).

## Enclosure and board layout

FB01 uses open nut recesses and flat adhesive mounting faces for four WAGO
connectors. The Raspberry Pi and paired level shifters use the R28 mounting
positions. The WAGO row is ordered W1, W3, W2, W4 from rear to front. Use the
current assembly drawing and electrical tables for connector orientation and
terminal assignments. Do not infer wiring from the connector order alone.

The front microphone grille uses four M3 × 6 screws and ordinary M3 nuts; the
rear grille uses M3 × 12. Front nuts are loaded before the audio cradle.
Rear vent, power jack and audio mounting recesses have open loading access.
Glue only the eight board nuts, four bottom-cover nuts and three audio-cradle
nuts. Hold the grille, rear-vent and power-jack nuts until their screws catch;
do not glue them. Fastener counts and allocations are maintained in
[hardware.json](../assembly/hardware.json).

## Head shelf

P08/P14 use the same three M3 × 8 screws and M3 nuts with the fastening
pattern rotated 60 degrees. Assemble this joint on the bench before installing
the head/mouth. The head shell remains unchanged; R34 replaces P31 as described above.

P08/P14 use direct native STL exports with closed edges at exact serialized
coordinates. Their source frames and the Fusion design are unchanged;
[export provenance](current/stl/head-export-provenance.json) records the checks.
An earlier P08 export sliced with an unintended center cap after tiny placement
changes. Preserve the replacement and check the opening in Preview; see the
[print lesson and tests](../printing/current/README.md#head-export-stability).

## Audio cradle

FB24 has a solid rear tape surface. Attach the USB module's rear face, opposite
the microphones, to that surface with tape under 1 mm thick. Do not cut open the
closed rear slits. Keep microphones exposed and follow the guide's module-first
installation sequence. The owner’s successful prototype does not establish tape
endurance or clearance for other USB modules and cables. R29 enlarges the USB
opening to 15.5 × 17.6 mm
and moves the left lid fastening 12.85 mm rearward onto a matching lid tab.
FB24 and FB32 change; the two M2 × 8 lid screws and base mounting stay the same.

## Backpack

P35 includes 1.5 mm hinge-root blends and tapered ribs extending outward up to
2 mm. Hinge gaps, pin seats and screw access are retained. Remove supports without
forcing the ears apart. Inspect support removal on each print; the digital
evidence does not establish loaded strength or fatigue life.

P36 canisters now have smooth 2 mm walls without internal fastening nuts.
The two corresponding P35 screw passages are closed. Bond the canisters at
the ring contact surfaces and bond the existing elbow/nozzle joints with
suitable epoxy. The two canister M3 × 8 screws and two M3 nuts are eliminated;
the backpack-to-carrier screws and belt joints remain removable.

## R29 downstream work

This is retained evidence for unchanged features, not an open task list. The
R29 preparation replaced seven P08/P14/FB24/FB32/P35/P36 instances and reviewed
full W1/W2/C2 slices. Five localized W1 blockers clear the P08 nut pockets and
relocated audio nut slot and screw bore. Accessible cradle and backpack hinge-gap
supports still need careful removal from each print. Guide images, instructions
and allocations include the six affected part families and omit the two retired
canister screws/nuts. Current print receipts retain the digital integration
checks; that preparation record itself included no physical print dispatch.

## Current print and rendering evidence

The [print procedure](../printing/current/README.md) describes selected projects,
settings and support removal. Its `checks/` directory retains compact digital
review evidence for the current geometry and inherited recipes. Whole-plate
estimates are predictions. Prior K1 support inspection covers the moved board
posts, nut recesses and WAGO mounting bands; W1 and W2 retain their documented
cradle and backpack reviews.

The [render source lock](../rendering/source-lock.json) selects the R34 assembly
mesh, native exports, palette and service-stand mesh. The stand originated in
R23; the renderer checks its transforms, body volumes and bounds against the
current assembly before reuse. A historical name does not imply a second design.

<a id="qualification-limits"></a>

## Evidence limits

The [safety notice](../SAFETY.md) describes the owner’s completed prototype and
build experience. Digital checks above do not establish fit, adhesive retention,
cable reach, strength, acoustic performance or powered safety for another build.
No comprehensive endurance or fault testing is established.

The selected print-source comparisons are recorded in the
[semantic review contract](../printing/recipes/README.md); the
[guide review summary](../build-guide/REVIEW.md) describes digital review scope.
No optional delivery snapshot is selected in the registry. This is a maintainer
record of selected inputs, not a certification or a physical kit offering.
