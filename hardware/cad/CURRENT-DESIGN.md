# Current Blue Glee Blob design

Open **Blue Glee Blob - MAIN** in Fusion → Admin Project.

Accepted design **R28**, exact cloud version **v24**.
Permanent file ID: `urn:adsk.wipprod:dm.lineage:nkM4P_10T7yYk-tasXlhbg`.

## CAD acceptance record

Recorded when this CAD revision was accepted; delivery status above may supersede downstream status below.

R28/cloud24 selects the straight WAGO row, Raspberry Pi and paired level-shifter mounts, and relocated fuse. Current print projects and guide use this geometry. Digital checks do not establish physical fit or complete harness qualification. See hardware/cad/CURRENT-NOTES.md.

## Current inputs

[Native assembly and selected exports](current/) · [Parts catalog](../catalog/parts.json) · [Print projects](../printing/current/) · [Build guide](../build-guide/README.md)

The registry selects CAD authority. Its mandatory input lock is checked even without a delivery. A delivery binds the print recipes, parts catalog and renders to that CAD; it does not approve physical fit. The build guide is not part of the release: it reads these files when it is built.

## Checks

`python3 hardware/cad/design_control.py check` validates the mandatory current set, accepted native and any selected delivery.

The [workflow](DESIGN-WORKFLOW.md) defines experiments, promotion and recovery.

No local check queries live Fusion or establishes print completion, fit, strength or optical acceptance.

Generated from [registry.json](design-control/registry.json); use the render command after a reviewed registry update.
