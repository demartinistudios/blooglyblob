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
