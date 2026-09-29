# Current hardware notes

The registry selects R28, Fusion cloud version 24. The native assembly, STL
exports and print projects are the maintained build inputs. Historical revision
names in current evidence identify the source of unchanged features.

## Enclosure and board layout

FB01 uses open nut recesses and flat adhesive mounting faces for four WAGO
connectors. The Raspberry Pi and paired level shifters use the R28 mounting
positions. The WAGO row is ordered W1, W3, W2, W4 from rear to front. Use the
current assembly drawing and electrical tables for connector orientation and
terminal assignments. Do not infer wiring from the connector order alone.

The front microphone grille uses four M3 × 6 screws and ordinary M3 nuts; the
rear grille uses M3 × 12. Front nuts are loaded before the audio cradle.
Rear, power-inlet and audio mounting recesses have open loading access and
adhesive nut retention. Fastener counts and allocations are maintained in
[hardware.json](../assembly/hardware.json).

## Audio cradle

FB24 has a solid rear tape surface. Attach the USB module's rear face, opposite
the microphones, to that surface with tape under 1 mm thick. Do not cut open the
closed rear slits. Keep microphones exposed and follow the guide's module-first
installation sequence. Actual tape adhesion and USB connector clearance remain
physical qualification items.

## Backpack

P35 includes 1.5 mm hinge-root blends and tapered ribs extending outward up to
2 mm. Hinge gaps, pin seats and screw access are retained. Remove supports without
forcing the ears apart. Printed strength and support removal require physical
qualification.

## Current print and rendering evidence

The [print procedure](../printing/current/README.md) describes selected projects,
settings and support removal. Its `checks/` directory retains compact digital
review evidence for the current geometry and inherited recipes. Whole-plate
estimates are predictions. Current K1 support inspection covers the moved board
posts, nut recesses and WAGO mounting bands; W1 and W2 retain their documented
cradle and backpack reviews.

The [render source lock](../rendering/source-lock.json) selects the R28 assembly
mesh, native exports, palette and service-stand mesh. The stand originated in
R23; the renderer checks its transforms, body volumes and bounds against the
current assembly before reuse. A historical name does not imply a second design.

## Qualification limits

Digital input checks, slicing and guide review do not establish printed fit,
adhesive retention, cable reach, mechanical strength, acoustic performance or
complete powered operation. The 48 independent print-source reviews currently
marked pending remain pending. See the [semantic review contract](../printing/recipes/README.md)
and [guide review summary](../build-guide/REVIEW.md). No synchronized kit delivery
is selected in the registry.
