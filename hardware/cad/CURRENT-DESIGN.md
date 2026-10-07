# Current Blue Glee Blob design

Open **Blue Glee Blob - MAIN** in Fusion → Admin Project.

Accepted design **R32**, exact cloud version **v28**.
Permanent file ID: `urn:adsk.wipprod:dm.lineage:nkM4P_10T7yYk-tasXlhbg`.

## CAD acceptance record

Recorded when this CAD revision was accepted; delivery status above may supersede downstream status below.

C04 display-only foam uses two round 14 mm shoulder holes and a continuous 2 mm rear seam. Windows, knife slits and edge notches are removed. Printed geometry, appearances, placements and all eight joints are unchanged. Native and STEP reimports verified.

## Current inputs

[Fusion assembly (.f3d)](current/assembly.f3d) · [STEP assembly (.step)](current/assembly.step) for other CAD applications.

[Native assembly and selected exports](current/) · [Parts catalog](../catalog/parts.json) · [Print projects](../printing/current/) · [Build guide](../build-guide/README.md)

The registry selects CAD authority. Its mandatory input lock is checked even without a delivery. A delivery binds the print recipes, parts catalog and renders to that CAD; it does not approve physical fit. The build guide is not part of the release: it reads these files when it is built.

## Checks

`python3 hardware/cad/design_control.py check` validates the mandatory current set, accepted native and any selected delivery.

The [workflow](DESIGN-WORKFLOW.md) defines experiments, promotion and recovery.

No local check queries live Fusion or establishes print completion, fit, strength or optical acceptance.

Generated from [registry.json](design-control/registry.json); use the render command after a reviewed registry update.
