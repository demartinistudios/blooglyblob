# Editable recipe checks

`python3 hardware/tools/printing/projects.py check` validates immutable project
bytes and archive integrity, settings, component/modifier meshes and transforms,
plate membership, build printability and catalog demand. The manifest-selected
download filenames must select exactly the validated recipe roles. `--json` returns structured readiness;
`--release` additionally requires the selected delivery and no outstanding source
review. `prepare --output <new-directory>` copies the complete accepted projects
and a baseline receipt. These commands never slice, dispatch or establish physical
qualification. Basic checks use Python's standard library and no installed Bambu
profiles.

`projects.json` binds the exact projects and `semantic-contract.json`. The whole-file
hash already protects every archive member; the historical member inventory is
not a second acceptance gate. Intentional edits require reviewing the changed
geometry/settings and updating the selected project identity. The latter
has persistent `recipe_instance_id` values assigned once, independently of Bambu
object IDs, labels and plates. Keep those stable identities through edits; update
the explicit numeric-object and plate mappings after review. Repeated labels are
valid. Duplicate stable IDs, reused numeric mappings and unassigned objects fail.
The mapping is a reviewed declaration, not an identity guessed from a label.

The source comparison uses the catalog-selected binary STL and a declared rigid
STL-to-raw-mesh frame, followed by the stored component and build transforms.
Every oriented triangle is compared, allowing vertex/triangle reordering and
welding of identical vertices. The 0.0001 mm coordinate tolerance covers the
recorded Bambu float roundtrip error below 0.000005 mm. Near-coincident ambiguous
matches require review. Different tessellation is unsupported; a topology mismatch
does not prove that the physical surfaces differ.

Each selected STL must also have nondegenerate triangles and closed,
consistently wound edges at its exact serialized coordinates. This check does
not round or tolerance-weld vertices: tiny open seams can make slicers fill
intended openings. It runs with `projects.py check`, including CI. It does not
prove absence of self-intersections or replace the affected full-plate slice
review.

The current contract verifies all 72 required/optional instance source meshes.
The projects reuse the selected downloadable STLs with independently reviewed
placement frames. No sampled surface-equivalence approvals are used. These checks
establish digital consistency; physical qualification remains separate.

## Replace a source mesh

Use the same accepted STL for the download and its print-project instances.
Do not make a second CAD export for the project or infer placement from its name.
Record the STL-to-project frame independently, including repeated instances.

The candidate-only helper consumes a hash-bound frame review:

```sh
python3 hardware/tools/printing/replace_meshes.py \
  --project baseline.3mf --review frame-review.json \
  --review-sha256 REVIEW_SHA256 --output NEW_DIRECTORY
```

The review declares `schema_version: 1`, `reviewer`, `method`, `project_sha256`,
a complete `instance_map` from stable instance IDs to Bambu object IDs, and
`replacements`. Each replacement supplies `recipe_instance_id`, a `source`
with `path` and `sha256`, and the reviewed 12-number `stl_to_mesh` matrix.
Source paths are absolute or relative to the review file.

The helper checks source identity and exact triangles while preserving unrelated
project content. It refuses unsupported mesh annotations instead of dropping
paint. Matching a supplied frame does not establish its intended orientation:
the independent frame review and candidate inspection establish that.
The output is a candidate, with affected preview caches invalidated. Follow the
[print procedure](../current/README.md#change-and-verify-a-recipe) to inspect and
re-slice affected plates before adopting it. The helper never updates current
files, changes Fusion, slices, or dispatches a print.

## Resolve an unsupported source comparison

After an independent reviewer establishes surface equivalence, add a JSON review
record and its frame evidence artifacts under `hardware/printing/recipes/reviews/`
in the same tracked change. Do not create an equivalence result until the actual
review is complete. Describe how the source frame maps to the raw normal component,
including component/build placement, and how different tessellations were compared.
The reviewer decides whether the method and stated limits justify equivalence.

The record must have this structure (placeholders below are documentation only):

```json
{
  "schema_version": 1,
  "reviewer": "Identified reviewer",
  "method": "Describe the actual independent surface/frame comparison and acceptance criteria",
  "result": "equivalent",
  "project_sha256": "<exact accepted whole-project SHA256>",
  "source_sha256": "<exact selected STL SHA256>",
  "recipe_instance_id": "<one persistent instance ID>",
  "frame_evidence": {
    "description": "Describe source and recipe frames and the verified mapping",
    "artifacts": [
      {
        "path": "hardware/printing/recipes/reviews/<frame-evidence-file>",
        "sha256": "<exact evidence SHA256>"
      }
    ]
  },
  "limitations": ["State method limits and any physical/support qualification excluded"]
}
```

For that one instance in `semantic-contract.json`, set `source_status` to
`reviewed_source_equivalence`, keep `stl_to_mesh` null, and add `source_review`
containing the record's repository-relative `path` and exact `sha256`. Preserve the
original `source_review_reason`. Update the contract hash in `projects.json` and
rebind selected delivery/current-input locks through the normal reviewed transaction.
Commit the record, every referenced artifact and the updated bindings together.
Offline validation works on an exported tracked tree without a Git index; it checks
location, content hashes and identities, while inclusion in the reviewed Git tree
is part of publication preparation.

The checker requires reviewer, method, an explicit `equivalent` result, exact
project/source/instance identities, frame evidence with at least one separately
hash-bound artifact, and declared limitations. Missing, failed, stale or edited
records/artifacts fail. Scratch, outside-directory and symlinked review
inputs fail. This disposition resolves only source geometry equivalence: immutable
project settings/modifiers/orientations, catalog demand, estimates, support review
and physical qualification keep their existing independent requirements. The current contract does not use surface-equivalence exceptions.

For a candidate roundtrip, provide separate JSON maps with `instances` and `plates`
objects, each mapping stable identity to its numeric Bambu ID string:

```sh
python3 hardware/tools/printing/semantics.py baseline.3mf candidate.3mf \
  --baseline-map baseline-map.json --candidate-map candidate-map.json
```

This strict comparison preserves global/plate/object/part settings, normal and
modifier triangle geometry, subtype, composed orientation and placement. Renumbered
objects/plates and changed labels are supported through the maps. Component
reordering, nested components, multiple build items for one object, intentional
setting or geometry changes require explicit review; no silently exempted parts
or positional object pairing is allowed.

Existing review evidence and inherited estimates retain independent `inputs`
bindings in the review receipt; updating a project/semantic lock alone makes the
old review stale. These bindings select the exact project
hashes and selected source hashes in the contract. An affected geometry or process
change invalidates those inputs and requires new bounded review and affected-plate
estimates. The preserved K1/C2 support audit sampled centerlines using the X1C Y+2
machine offset; it is neither a generic support checker nor proof of full bead
clearance. No slice determinism, completed print, fit or installed state is inferred.
