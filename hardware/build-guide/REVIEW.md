# Guide review scope

The guide uses R28 / Fusion cloud24 inputs. The
[review checklist](review-status.json) records digital review by surface, separate
from physical build qualification. A verified entry applies to the recorded
revision; changing a surface or its inputs requires a fresh review.

The current review covered:

- Assembly order, mating orientation, fastener entry and access before closure.
- Part/supply cards, hardware quantities, plate previews and generated downloads.
- All 89 raster illustrations, including magnet installation, servo-horn fastening,
  speaker and connector geometry, wire continuity, tool drawings and glue locations.
- Electrical reference and master diagram, including button terminals and head
  power branches, against maintained electrical tables.
- Software commands and nine Raspberry Pi setup screenshots.
- Stable step IDs, progress storage, navigation, responsive layout and the header
  links at desktop and phone widths.

The recorded contributor check passed software formatting, lint, types and tests,
hardware tooling checks, guide generation and browser checks. The later header
review covered seven widths from 320 to 1440 pixels, pointer hover and keyboard
focus. Browser checks covered 612 route/viewport combinations, 138 links and
316 images. These figures describe the reviewed version, not a test-count target.

Run `make check` to verify the current checkout. It checks data consistency and
browser behavior; it cannot determine whether every illustrated action is
physically correct. A visual review must compare drawings with the selected CAD
and instructions, rather than treating a successful render as evidence of fit.

Physical assembly, tape and glue retention, actual connector clearance and cable
slack, acoustic behavior and complete powered operation remain unqualified.
The separate pending print-source comparisons are not cleared by guide review.
See [current hardware notes](../cad/CURRENT-NOTES.md) and the
[release checklist](../../../docs/release/checklist.md).
