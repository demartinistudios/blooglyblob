# Guide review scope

The guide consumes the accepted CAD and print inputs selected by the
[registry](../cad/design-control/registry.json). The
[review checklist](review-status.json) records digital review by surface,
separate from physical assembly acceptance and website deployment.

## Current assembly update

The mouth uses a printed holder (P31), rear cover (P30) and a captured LED board.
Two M2×8 screws engage two head-mounted M2 nuts; there are no separate PCB screws
or mouth washers. The white LD45 diffuser is 4 mm thick, trimmed to 5.75 mm high.

The upper support collar (P44) uses the existing two M3×10 screws and upright
nuts. The lower collar remains P01, quantity one. A clear-film bearing disc rests
on P44 with two folded tabs in its slots. The full-size template has an 82.6 mm
outer diameter, 62 mm inner circle and two 3.2 mm-wide tabs with a 2.5 mm fold.
The eye windows and bearing disc share the C01 film supply and one shopping-sheet
allowance. The cost calculation includes a separate blank for the disc.

The owner accepts the assembled mechanical hardware. This is not a blanket
qualification of electrical protection, thermal behavior or every operating
condition. The broad manual review remains pending; focused changes do not
silently clear unrelated checklist entries.

The release review covers matching part identities and counts, fastening order,
PCB orientation, foam placement, film preparation, collar slots, screw access,
neighboring head-mounting steps, material allowances and template scale.
The updated illustrations use R34 / Fusion cloud version 32. The mouth views
show foam insertion, board capture, head-nut loading and the two-screw assembly;
the collar views show its screw seats and the bearing-film tabs. Board colors
identify the eight LED packages without changing any source triangles. The
obsolete mouth section has been removed. The template was checked at actual
PDF/SVG size, and the screw keys were regenerated from current allocations.

The print instructions match the selected production package: 70 pieces across
53 required part types on 10 plates, with all 71 required and optional source
instances compared to the selected exports. Plate previews and downloadable
STLs/3MF are bundled from those current inputs. Head-horn fastening now calls for
gentle seating without overtightening to eliminate slight left–right rotational
play, viewed from above. The check uses a light touch, without forcing the servo
shaft to turn.

## Validation boundaries

The [render source binding](../rendering/source-lock.json) identifies the mesh
and CAD revision used for assembly illustrations. Review mating surfaces,
insertion directions and tool access visually; a successful renderer is not
proof of a correct instruction. The presentation image and decorative homepage
lighting illustrate the completed robot, rather than fastening or optical
performance.

The guide consistency check covers quantities, hardware allocations, step links,
documented commands and writing constraints. The print recipe checks compare
selected meshes with the catalog sources. STL downloads, project downloads,
plate previews and filament estimates are derived from the maintained print
inputs through the [print procedure](../printing/current/README.md).

Run `make check` for the current checkout's software, hardware, guide and browser
checks. Those checks neither operate a device nor establish physical fit or
powered safety. See [current hardware notes](../cad/CURRENT-NOTES.md) and the
[release checklist](../../../docs/release/checklist.md) for their separate scope.
