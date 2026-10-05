# Current hardware notes

The registry selects R31, Fusion cloud version 27. The native assembly, STL
exports and print projects are the maintained build inputs. Historical revision
names in current evidence identify the source of unchanged features.

## Portable assembly

Download the [Fusion assembly (.f3d)](current/assembly.f3d) or the
[STEP AP214 assembly (.step)](current/assembly.step). The STEP exports the full
R31/cloud27 assembly, including hidden reference, layout and test components.
Reimport into Fusion retained all 563 bodies and 331 occurrences in their assembly
positions. It contains geometry and component placements, without Fusion
parametric history or joints. Body names and occurrence suffixes may change on import.
[Export provenance](current/step-export-provenance.json) records the source,
hash and measured reimport checks.

## Electrical references

The assembly contains one lighting fuse holder, F2, in its accepted location.
Printable geometry, supports, component placements and all eight arm joints are
unchanged. See [native verification](current/evidence/fuse-reference-r31.json)
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
the head/mouth. The head shell and P31 remain unchanged.

P08/P14 use direct native STL exports with closed edges at exact serialized
coordinates. Their source frames and the Fusion design are unchanged;
[export provenance](current/stl/head-export-provenance.json) records the checks.

## Audio cradle

FB24 has a solid rear tape surface. Attach the USB module's rear face, opposite
the microphones, to that surface with tape under 1 mm thick. Do not cut open the
closed rear slits. Keep microphones exposed and follow the guide's module-first
installation sequence. Actual tape adhesion and USB connector clearance remain
physical qualification items. R29 enlarges the USB opening to 15.5 × 17.6 mm
and moves the left lid fastening 12.85 mm rearward onto a matching lid tab.
FB24 and FB32 change; the two M2 × 8 lid screws and base mounting stay the same.

## Backpack

P35 includes 1.5 mm hinge-root blends and tapered ribs extending outward up to
2 mm. Hinge gaps, pin seats and screw access are retained. Remove supports without
forcing the ears apart. Printed strength and support removal require physical
qualification.

P36 canisters now have smooth 2 mm walls without internal fastening nuts.
The two corresponding P35 screw passages are closed. Bond the canisters at
the ring contact surfaces and bond the existing elbow/nozzle joints with
suitable epoxy. The two canister M3 × 8 screws and two M3 nuts are eliminated;
the backpack-to-carrier screws and belt joints remain removable.

## R29 downstream work

CAD is accepted. Guide images, instructions and supply allocations now reflect
all six affected part families, including removal of two canister screws and
two nuts. Scoped digital guide review and focused checks passed. Print preparation
replaces all seven P08/P14/FB24/FB32/P35/P36 instances and includes full W1/W2/C2
slicing and digital support review. Five localized W1 support blockers clear the
P08 nut pockets and relocated audio nut slot and screw bore. Accessible cradle
supports and backpack hinge-gap supports still require removal. Final package
integration and combined checks are recorded in the current printing receipts;
no physical print was dispatched as part of this preparation.

## Current print and rendering evidence

The [print procedure](../printing/current/README.md) describes selected projects,
settings and support removal. Its `checks/` directory retains compact digital
review evidence for the current geometry and inherited recipes. Whole-plate
estimates are predictions. Prior K1 support inspection covers the moved board
posts, nut recesses and WAGO mounting bands; W1 and W2 retain their documented
cradle and backpack reviews.

The [render source lock](../rendering/source-lock.json) selects the R31 assembly
mesh, native exports, palette and service-stand mesh. The stand originated in
R23; the renderer checks its transforms, body volumes and bounds against the
current assembly before reuse. A historical name does not imply a second design.

## Qualification limits

Digital input checks, slicing and guide review do not establish printed fit,
adhesive retention, cable reach, mechanical strength, acoustic performance or
complete powered operation. All 72 required/optional print-source comparisons
now pass; none remain pending. See the [semantic review contract](../printing/recipes/README.md)
and [guide review summary](../build-guide/REVIEW.md). No synchronized kit delivery
is selected in the registry.
