# Editable print recipes

The current package is **R29 / Fusion cloud25**: ten color/material plates,
71 required pieces / 51 types. Open **BlooglyBlob-R29-PLA-Production.3mf** in
Bambu Studio 2.7.1.62. The optional clear PETG ball project replaces A05 on T1.
Logical filament numbers are profiles, not physical AMS slot assignments.

The selected enclosure layout provides four Pi posts, four shifter posts and
four WAGO mounting pads. See [current CAD notes](../../cad/CURRENT-NOTES.md).

K1 estimate: **12h 14m 24s, 289.52 g**.
Package estimate: **39h 1m 54s, 685.50 g**.
Eight affected PLA plates and the optional PETG ball were re-sliced after mesh
reconciliation. K1 and B2 estimates are inherited from their unchanged recipes. These are slicer estimates, not measured outcomes.

The set is digitally prepared. All 72 required/optional source-instance comparisons pass exact triangle checks.
Physical qualification remains separate; use `python3 hardware/tools/validation/check.py
--publication` for current blockers. Support release, nut fit, adhesive retention
and installed wiring need physical qualification before a validated-kit claim.

## Source mesh reconciliation

The downloadable STLs and all 72 required/optional normal meshes now agree
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
| W1 — white, plate 1 | R29 head pair and audio cradle/lid; retained 0.16 mm layers, tree supports and brims | 3h 27m 10s, 64.26g |
| K1 — black, plate 2 | R28 shell roof-down; 0.20mm layers, 4 walls, 25% gyroid, 5mm outer brim / 0.12mm gap; normal/snug supports, 0.20mm Z / 0.40mm XY; PLA 220°C nozzle / 60°C textured PEI | 12h 14m 24s, 289.52g |
| W2 — white, plate 3 | R29 glue-retained backpack; existing settings and pin blockers retained | 4h 12m 45s, 65.95g |
| C2 — copper, plate 7 | R29 canisters upright; silk PLA 220°C / 55°C, 7.5 mm³/s; all other copper parts/settings retained | 3h 44m 26s, 48.63g |

Use the project and object-settings.csv for each object's overrides. K1 flow
calibration stays OFF because the layout intersects the calibration region at
Y12. The generic PLA bed-temperature warning remains. Confirm the X1 Carbon,
0.4mm nozzle, textured plate and selected material before printing.

The selected fingers-up/peg-down hands, side-down arm cores, front-down goggles,
collar inner-and-outer 8mm brims, P35 pin blockers, unsupported upright P10 and
antenna thread protection remain. Copper silk settings, including the C2
220°C nozzle / 55°C bed and 7.5mm³/s flow limit, are preserved. K1 and B2 plate estimates are inherited. The optional PETG ball uses the same
selected A05 mesh as the PLA project, with its own retained PETG process and a
fresh slice estimate of 22 m 25 s / 1.36 g.

## Support removal and assembly checks

K1 has four switch, six front and four rear blockers, plus one narrow
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
binds this update to the registry-selected CAD. checks/r29-mesh-consistency-* records current source/frame, fullplate and support review. Earlier checks/r29-* retains prior W1/W2/C2 review and arm frame corrections; checks/r28-* retains the unchanged K1 review; checks/r27-* preserves prior nut-slot evidence; checks/r26-* preserves W1; checks/r25-* preserves W2, and checks/r24-* preserves the preceding
base/cradle review. Other checks files preserve explicitly historical R23 evidence
for inherited recipes; they are not new R29 results. PUBLISHED.json is a current
file inventory, not proof of deployment or user approval. Git preserves superseded
project versions; current/ keeps only the selected pair.

Save experimental edits under ignored hardware/.work/. Before adopting a saved
project, use `hardware.tools.printing.privacy.sanitize_project(source, output)`
and `check_project(output)` on a separate candidate. These remove only nonempty
DesignerUserId metadata; verify geometry/settings preservation independently.
