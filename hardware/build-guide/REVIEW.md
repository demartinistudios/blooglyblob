# Guide review scope

The guide selects R31 / Fusion cloud27 inputs. The
[review checklist](review-status.json) records digital review by surface, separate
from physical build qualification. Its broad review remains pending after the
build guide clarity overhaul; the focused updates below do not clear that review.

The retained R29 digital review covers the six changed part designs P08, P14, FB24,
FB32, P35 and P36:

- Shelf and adapter fastening axes match the accepted native bores. Screws enter
  from above and nuts sit beneath the shelf, assembled on the bench before the head.
- Cradle and lid illustrations show the asymmetric lid fasteners and enlarged USB
  opening. The connector illustration uses the measured loose connector envelope;
  endpoint locators do not assert a final mated position or cable bend.
- Tank assembly shows epoxy at the hidden ring contacts. The completed backpack
  stays removable with its four carrier screws. Installed quantities and both
  screw-key PDFs agree on five M3×8 screws and 60 M3 nuts.
- The affected part cards, assembly/service close-ups, base layouts and full-robot
  view were regenerated and visually reviewed. The base-cover view was regenerated
  and remained identical. Unchanged local interfaces and unrelated views were
  retained after dependency review.

The electrical instructions specify a direct 18 AWG servo feed from W1/3 to
W2/1, one F2 T1 A lighting fuse and the exact GST40A05-P1J supply. Service
instructions isolate servo power at W1/3 and restore it before final inspection.
The current native and STEP exports contain one lighting fuse reference.
The printed geometry, STLs, print projects and plate previews are unchanged.
Affected guide surfaces remain pending review; these instructions do not
establish physical qualification.

The [render source binding](../rendering/source-lock.json) records the reviewed
coordinates and accepted CAD identity. Native-bore regression tests check the
shelf and lid fastening axes. The guide consistency check covers allocations,
step references and writing constraints. Print projects and their plate previews
are maintained through the [print procedure](../printing/current/README.md).

Run `make check` to verify the current checkout. It checks data consistency and
browser behavior; it cannot determine whether every illustrated action is
physically correct. A visual review compares drawings with the selected CAD and
instructions, rather than treating a successful render as evidence of fit.

Physical assembly, tape and glue retention, actual connector clearance and cable
slack, acoustic behavior and complete powered operation remain unqualified.
All 72 print-source comparisons now pass the separate print recipe checks.
The STL downloads, plate previews and estimates are derived from those inputs.
P08/P14 now use closed native STL exports from the same R29 design. The W1
project and its derived downloads/preview were refreshed after full-plate slice
review. Native render geometry, assembly instructions and fastener locations
remain unchanged. Exact serialized edge checks supplement source matching;
they do not establish physical fit or rule out every slicer failure.
See [current hardware notes](../cad/CURRENT-NOTES.md) and the
[release checklist](../../../docs/release/checklist.md).
