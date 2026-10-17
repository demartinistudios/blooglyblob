# Guide review scope

For agents reviewing guide changes. Builders should follow the
[illustrated guide](https://demartinistudios.github.io/blooglyblob/) and
[Safety & responsibility](../SAFETY.md).

On 2026-10-16, the owner reported building and testing one complete prototype
and revising the build guide based on that experience. This does not
establish comprehensive electrical, thermal, endurance or fault testing.

The guide may contain errors or omissions. The notes below describe completed
work and useful technical lessons, not a certification or a future testing plan.

## Current assembly update

The focused R34 / Fusion cloud32 review covers the P30/P31 mouth and P44 upper
bearing collar. [CAD notes](../cad/CURRENT-NOTES.md#mouth-and-upper-bearing-collar)
retain their dimensions, fastening and assembly constraints. P01 remains the
lower collar. The eye windows and bearing disc share C01 film and one shopping
allowance, with a separate disc blank included in the cost calculation.

Review covered identities/counts, fastening order, PCB orientation, foam and film
placement, collar slots, screw access, adjacent head steps, material allowances
and actual PDF/SVG template scale. Screw keys were regenerated from allocations.
The eight LED-package colors clarify the board without changing source triangles.
The full-character still, homepage animation base and social card use the R34
collar’s native pose with existing lighting and framing; the
[presentation record](../rendering/presentation-front.json) retains source and hashes.

The recorded print review covers 70 pieces across 53 required types on 10 plates,
with all 71 required/optional source instances compared to selected exports.
Head-horn fastening calls for gentle seating without overtightening to eliminate
slight left–right rotational play, viewed from above. Check with a light touch;
do not force the servo shaft to turn.

## Fastener sourcing and head styles

The October 17 guide uses Kadrick M3 socket-head kit B0B51BFSWZ,
Kadrick M2 button-head kit B0BX96SMW4 and iexcell M3×14 button-head pack
B08H2HQ3VZ. The [reference catalog](../references/community-20260925/catalog.json)
links the selected products. The owner built with these kits, confirmed button
heads at the front post and accepted the installed tip clearance. The exact
length at every original joint was not recorded; the current allocation uses
five M3×14 buttons and three M3×20 sockets to match available stock and the
reviewed interfaces. No CAD geometry or print input changed.

Current-R34 envelope checks support the M3×20 backpack substitution and the
M3×14 button at the sideways front carrier and elbows. The front-light buttons
bear at the tapered openings and remain raised. The upper screw's idealized
tip overlaps the servo reference by 0.05 mm; the owner's assembled-clearance
confirmation is the physical evidence for retaining that screw. Do not force
these heads flush. The owner omitted the speaker washers; the guide now seats
the nuts directly against the speaker tabs and retains gentle-tightening checks.

The owner-measured M3 socket-head sample was Ø5.33 × 3.03 mm; the selected
iexcell listing gives Ø5.5 × 1.53 mm for its button head. Sample and listing
dimensions are not manufacturing limits. Exact M2 head and kit-washer dimensions
remain unmeasured. The guide retains four eye washers and its existing M2×10
eye-mount screws, with a check for clamping and bottoming; it does not establish
a newly measured eye stack. Illustrations show nominal hardware, and the screw
keys gauge under-head length rather than certify head or washer dimensions.

Mixed-kit purchases are calculated by component capacity. Material values use
equal-per-piece allocation, with row rounding, as described in
[Build cost](../catalog/BUILD-COST.md). Prices are dated quotes excluding freight.

## Loose wire and supplied cables

The guide buys one 10 ft continuous length of CNC Tech black stranded 18 AWG
UL 1007 PVC wire from DigiKey (1007-18-1-2000-001-1-TS),
for new power leads and optional extensions. It retains supplied servo, GPIO,
lighting and audio leads at their original gauges. The owner reports that the
servo and lighting leads reached without extensions; routing still determines
whether a builder needs extra length. Optional splices remain insulated and
clear of moving bends. The specified Pi power cable retains its 150 mm maximum
finished length and must not be extended.

The manufacturer datasheet states RoHS and REACH compliance, 300 V / 80 °C
ratings and 34/0.18 mm tinned-copper strands. The PVC jacket is suitable for
these internal hookup leads; supplied moving cable assemblies remain in use.
New wires need labels at both ends; schematic colors denote circuit functions.
The 2 m loose-wire allowance is an estimate with spare, not a measured cut list.
The separate tie, heat-shrink and adhesive-mount purchases remain unchanged.
No circuit topology, connector specification, CAD geometry or print input changed.

## Validation boundaries

The [render source binding](../rendering/source-lock.json) identifies illustration
inputs. Review mating surfaces, insertion directions and tool access visually;
a successful renderer does not establish instruction correctness. Presentation
images and decorative lighting do not demonstrate fastening or optical performance.

Guide consistency checks cover quantities, allocations, links, commands and
writing constraints. Print checks compare selected meshes with catalog sources;
the [print procedure](../printing/current/README.md) owns the inputs used for plate
previews, estimates and download packages. `make check` checks software, hardware,
guide and browser behavior without operating a device or establishing physical
fit or powered safety. See [CAD notes](../cad/CURRENT-NOTES.md) and the
[release checklist](../../docs/release/checklist.md) for scope.

## Publication notices and downloads

The guide renders the canonical [safety notice](../SAFETY.md). Start, preparation
and printing pages state prototype/support limits. Printing offers only the
complete Bambu and STL ZIPs, each carrying portable safety/licensing documents;
raw print files are inside those packages. Part-catalog links remain, including
the optional pointing hand. These changes alter no geometry or print settings.

## Lessons for future edits

- The Pi header was previously mirrored. From the pin side, even pins are on
  the board-edge row and odd pins on the inner row; count from the microSD end.
  Step drawings and the complete wiring diagram must agree.
- JST-SM pins sit inside the larger shroud; the smaller sockets half slides into
  it. Show the latch and viewing direction. Use continuity and strand-input
  checks, not drawn wire colors, to establish connections.
- Preserve access-dependent assembly order and the powered fit sequence:
  seat horns while the command holds, then STOP, shut down and unplug before
  fastening center screws. Follow current steps for refitting and closing.
- Draw the state the action leaves, including insulation and bench/towel support.
  Keep explanatory prose in captions. Follow the
  [instruction design rules](INSTRUCTION-DESIGN.md).

Current steps and catalogs own detailed wiring, fastening and supply facts.
