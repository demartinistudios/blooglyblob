# Editable print recipes

The current CAD is **R34 / Fusion cloud32**, with ten color/material plates,
70 required pieces / 53 types. Open **BlooglyBlob-R34-PLA-Production.3mf** in
Bambu Studio 2.7.1.62. The optional clear PETG ball replaces A05 on T1.
Logical filament profiles are independent of physical AMS slots.

Package estimate: **40h 7m 21s, 687.32 g**. K1 and C1 were freshly
sliced for this release; eight other plates retain their verified prior estimates.
All 71 required/optional source-instance comparisons pass exact triangle and
closed-topology checks. See [current review](checks/r34-mouth-collar-validation.json).

## R34 mouth and upper collar

K1 contains the enclosure, **P30 rigid rear cap** and **P31 eight-channel mouth
holder**. Both mouth parts print rear face down at 0.16 mm layers, with 0.20 mm
first layer, five walls and a 5 mm outer brim / 0.12 mm gap. P30 uses 100%
rectilinear infill and no supports. P31 uses 35% gyroid and bed-only snug supports;
a central blocker keeps supports out of the channels, diffuser pocket and board
recess. Remove the two short, exposed supports below its mounting ears before
assembly. The holder and cap use the existing two M2×8 screws and nuts.

The whole K1 logical black PLA profile uses **220°C nozzle / 60°C bed / 8 mm³/s**,
retaining the mouth trial's flow limit. Its full-plate estimate is **13h 0m 17s /
288.82 g**. The enclosure geometry, orientation and support blockers are retained.
Flow calibration stays off for K1 because its layout crosses that calibration area.

C1 contains one unchanged **P01 lower collar** and one **P44 upper bearing collar**,
plus the retained arm cores and goggles. P44 prints bearing face down, groove up:
0.20 mm layers, five walls, 35% gyroid, supports off, 8 mm outer brim / 0.08 mm gap.
The copper silk profile remains **220°C / 60°C / 6 mm³/s**. Clear only the two
0.20 mm sacrificial screw-hole membranes; preserve the surrounding seats and
bearing surface. The bearing film is cut using the guide's 1:1 template and is
not a printed part. C1's full-plate estimate is **5h 35m 22s / 54.84 g**.

[Full-plate first layers](checks/r34-first-layer.png) show separate brims and
support footprints. [Mouth support review](checks/r34-mouth-supports.png) confirms
accessible ear pads, with no sampled support inside the channels. Assembly feedback,
digital geometry checks and material-specific printing results are recorded separately.

## R33 lighting and head carrier

W1 contains P43 FRONT upright and reinforced P04 carrier. W2 contains the
unchanged P02 REAR upright, P11 LOWER, P42 UPPER and P12 MIDDLE light brackets.
Each is quantity 1. P13 front wire guide is retired. P41 is a historical grille
identity and must not be used for the front upright. The P10 foam seam covers
remain unchanged. Historical recipe instance IDs are preserved; explicit part
IDs in the manifest and catalog identify the new parts.

P43 prints rear face down with countersinks up: 0.20 mm layers, 5 walls, 25% gyroid,
supports off. P04 prints servo-seat face down: 0.16 mm, 5 walls, 25% gyroid; automatic
trees remain enabled but this slice generates no carrier support. Both use a
3 mm outer brim with 0.1 mm gap. The carrier's horizontal screw bores bridge;
check bridging and nut fit after cleanup. The front post's M3×10 countersunk
screw is nominal design sizing, not an owner-confirmed installed length; check
full nut engagement. Rear M3×20 remains unchanged.

P11/P42/P12 print upright with accessible nut-entry openings: 0.20 mm layers,
4 walls, 25% gyroid, 3 mm outer brim / 0.1 mm gap, automatic trees with 0.20 mm Z and
0.35 mm XY separation. Lower/upper inset nut-entry and mounting-bore support
samples are clear. Accessible supports remain below arms/pads and in the middle
bracket bore. Hold the arms while clipping supports; avoid twisting the pads.
White PLA profiles stay 220°C nozzle / 55°C textured bed / 12 mm³/s.

The lower and middle brackets are spaced apart on W2; its rear upright moves
6 mm inward to give the brim clearance from the excluded bed corner. All other
objects retain their geometry, process and placement; existing support blockers
are preserved. The retained head opening and screw-bore support cores were
reviewed again. See the [first layers](checks/r33-first-layer.png),
[support review](checks/r33-support-review.png) and
[carrier layers](checks/r33-carrier-layers.png).

## Retained source mesh reconciliation

The downloadable STLs and all 71 required/optional normal meshes now agree
triangle-for-triangle in independently reviewed frames. Forty-one retained recipe
instances were normalized without changing their print settings, orientation,
placement or support modifiers. A04 uses a closed native STL export from the
unchanged R29 design. P08/P14 also use clean direct-native exports of the unchanged R29 bodies. Other selected sources are retained.

Belt supports remain in open clevis gaps and beneath raised hinge ears; the
sampled 1.0 mm pin cores through solid knuckles are clear. Support the ears while
clearing those gaps before inserting pins. Full-height blocker envelopes are not
a promise that every open gap contains no support. Physical cleanup and fit still
need checking.

## Head export stability

P08/P14 use clean native exports of the same R29 geometry. The previous P08
mesh could slice with an unintended cap across its center opening after a tiny
placement change. The replacement passed seven shifted head-pair slices, a fresh
desktop slice and full W1 review. Settings, orientation, blockers and screw
locations are unchanged. Review the opening in Preview after slicing; exact
source matching alone does not establish closed topology or slicer stability.
See checks/r29-head-topology-validation.json for scope and limits.

## R29 changes and cleanup

P08 and P14 use the new three-screw pattern. Fit them together on the bench
with the head and mouth removed. FB24 and FB32 provide the wider USB entrance
and moved left lid fastener; print them as a matched pair. P35 and both P36
canisters omit the inaccessible tank screw/nut features. Bond the hidden
tank-to-ring contact surfaces and the existing elbow/nozzle joints; the complete
backpack remains removable. Individual tanks become permanent.

Five localized support blockers keep the underside P08 nut pockets and the moved
audio lid nut slot/bore open. Inspect the small bridge roofs and clear stray
threads before seating nuts. Accessible supports remain around the audio ends
and in the backpack hinge gaps; support the ears while removing them. Do not
cut the intentionally closed cradle tie slits or the now-filled tank screw holes.

## Audio cradle and backpack cleanup

The closed cradle tie slits are solid design material; do not cut them back open.
Remove ordinary end supports without gouging the tape-facing rear wall or bearing
surfaces. Tape under 1 mm bonds the dongle rear face to the inside rear cradle wall,
not the deck or lid. Actual tape bond and USB connector/end-window fit are still
unqualified. Keep the bare-module-first and actual-connector-fit checks in the guide.

The backpack pin-seat cores remain clear in sampled paths, while
support remains in the open hinge gap. Support the ears
while cleaning those regions before inserting pins. Strength and support
release still require physical testing.

## Change and verify a recipe

Follow the [hardware workflow](../../README.md) for authority and retention.
The [manifest](manifest.json) selects the current projects and plate metadata;
[recipe locks](../recipes/projects.json) bind their exact bytes and instances.

1. Record the accepted CAD/recipe baseline and affected stable instances. Copy
   the complete project into a new ignored run with
   `python3 hardware/tools/printing/projects.py prepare --output hardware/.work/printing/NEW_RUN`.
2. Use the [candidate-only mesh helper](../recipes/README.md#replace-a-source-mesh)
   with independently reviewed source frames, or replace affected normal meshes
   in Bambu Studio. Preserve unrelated
   orientations, transforms, modifiers, blockers, inherited settings and object
   overrides. Reconcile persistent instance IDs if Bambu renumbers objects;
   labels alone cannot identify repeated instances.
3. Re-slice every affected complete plate. Review fit-critical cavities,
   supports, correct source frames, bed bounds and unchanged instances. Record
   tool/version, machine/nozzle/plate/material, process and coordinate offsets.
   Estimates are predictions, not measured outcomes. Changed geometry, material
   or machine invalidates previous toolpaths.
4. Update metadata/evidence and run
   `python3 hardware/tools/printing/projects.py check` and `make hardware-check`.
   Byte and structure checks do not replace support/toolpath review. Run
   `make check` before a completed implementation handoff.
5. Send the affected guide owner one handoff with quantities, estimates,
   settings, previews and limits. The guide derives project downloads, ZIPs and
   plate thumbnails from these maintained inputs; do not create competing copies.

For publication add `--release`; all independent source reviews and a selected
delivery must be resolved. The [semantic review contract](../recipes/README.md)
describes explicit equivalence evidence. Never clear a pending review simply by
updating hashes. Actual dispatch is separately authorized. Keep its results, printer queues and
stock records in ignored local `hardware/printing/operations/`; they are not
required public build inputs.

## Affected plates and retained process

| Plate | Recipe and change | Whole-plate estimate |
|---|---|---|
| W1 — white, plate 1 | R33 carrier/front upright; retained head/audio parts and blockers | 3h 28m 30s, 64.67g |
| K1 — black, plate 2 | R34 rear-down P30 cap/P31 holder with retained roof-down shell; black PLA 220°C / 60°C / 8 mm³/s | 13h 0m 17s, 288.82g |
| W2 — white, plate 3 | R33 lower/upper/middle LED brackets; rear upright and backpack retained | 4h 7m 44s, 60.76g |
| C2 — copper, plate 7 | R29 canisters upright; silk PLA 220°C / 55°C, 7.5 mm³/s; all other copper parts/settings retained | 3h 44m 26s, 48.63g |

Use the project and object-settings.csv for each object's overrides. K1 flow
calibration stays OFF because the layout intersects the calibration region at
Y12. The generic PLA bed-temperature warning remains. Confirm the X1 Carbon,
0.4mm nozzle, textured plate and selected material before printing.

The selected fingers-up/peg-down hands, side-down arm cores, front-down goggles,
P01 inner-and-outer 8mm brims and P44 outer-only 8mm brim, P35 pin blockers, unsupported upright P10 and
antenna thread protection remain. Copper silk settings, including the C2
220°C nozzle / 55°C bed and 7.5mm³/s flow limit, are preserved. B2 retains its prior estimate; K1 was re-sliced for R34. The optional PETG ball uses the same
selected A05 mesh as the PLA project, with its own retained PETG process and a
fresh slice estimate of 22 m 25 s / 1.36 g.

## Support removal and assembly checks

The K1 enclosure has four switch, six front and four rear blockers, plus one narrow
full-height blocker protecting both power nut slots and their screw bores.
Sampled paths show clear board/cover nut insertion regions. The FB24 tie slits
are intentionally closed. Small accessible front entry-edge support remains
above one lower seat; trim it before inserting the nut. Do not gouge a bearing surface to force fit.
Small rear roof bridges and the new pockets still need a real print/cleanup check.

The unchanged front grille uses four M3×6 screws and ordinary M3 nuts, no washers;
the rear grille uses M3×12. Load the front nuts before the audio cradle. Rear, power and audio nuts use open
slots with glue retention. Validate actual nut fit,
glue pull-out and screw engagement. Four WAGOs attach to the mounting pads with tape. Tape grade/thickness, adhesion on printed faces, adhesive tie mounts
and the full audio restraint route need physical qualification. Slicing establishes
none of these outcomes.

## Files and evidence

manifest.json, object-settings.csv and planned-settings.json describe the selected
recipe. source-provenance.json retains inherited recipe origins; live-source-check.json
binds this update to the registry-selected CAD. checks/r34-mouth-collar-validation.json records the current K1/C1 source, support and preservation review. checks/r33-lighting-validation.json retains W1/W2 evidence for unchanged scope. Earlier checks/r29-mesh-consistency-* records prior source/frame and support review, reused only for unchanged scope. Earlier checks/r29-* retains prior W1/W2/C2 review and arm frame corrections; checks/r28-* retains prior enclosure geometry/support evidence within K1; checks/r27-* preserves prior nut-slot evidence; checks/r26-* preserves W1; checks/r25-* preserves W2, and checks/r24-* preserves the preceding
base/cradle review. Other checks files preserve explicitly historical R23 evidence
for inherited recipes; they are not new R29 results. PUBLISHED.json is a current
file inventory, not proof of deployment or user approval. Git preserves superseded
project versions; current/ keeps only the selected pair.

Save experimental edits under ignored hardware/.work/. Before adopting a saved
project, use `hardware.tools.printing.privacy.sanitize_project(source, output)`
and `check_project(output)` on a separate candidate. These remove only nonempty
DesignerUserId metadata; verify geometry/settings preservation independently.
