# CAD experiments, promotion and recovery

Start with the [hardware workflow](../README.md), then read
[CURRENT-DESIGN.md](CURRENT-DESIGN.md) and its source,
[registry.json](design-control/registry.json). The registry selects the only
accepted MAIN by permanent Fusion file ID, exact design release and cloud
version. Names, timestamps, larger revision numbers and the active tab do not
establish authority. Design revisions and Fusion cloud save versions are separate
sequences. Never create another MAIN with Save As.

## Propose and test a change

1. Run `python3 hardware/cad/design_control.py check` from the repository root.
   Read the selected release, current input lock and [current notes](CURRENT-NOTES.md).
2. When using live Fusion, inspect file ID, saved/latest cloud version,
   processing completion and unsaved changes. The offline checker cannot do
   this. Preserve and reconcile any discrepancy before mutation.
3. Work in a separate experiment document and unique ignored
   `hardware/.work/experiments/<topic>/<run-id>/`. Record owner, intent, parent
   release/hash, cloud identity if available, expected changed parts/interfaces,
   acceptance criteria, checks, limitations and disposition. Contributors without
   MAIN access can submit their candidate and evidence for maintainer review.
4. Use `python3 hardware/tools/cad/impact.py PART_ID` as a starting point for
   affected plates, scenes, steps and interfaces. Review mating parts without
   automatically changing them. Keep eye-local, assembly and bed frames explicit.
5. Record actual trial results separately from predictions. Preserve the exact
   native/project/settings identity of printed trials. Use the maintained export
   helpers below; verify their explicit input identity before use.

## Promote the accepted scope

Only the authorized promotion owner updates MAIN. The local lock is cooperative;
it does not prevent another Autodesk user from editing. Other owners may continue
isolated experiments and downstream work without holding this lock.

1. Record scoped acceptance, baseline and expected outputs. Acquire the lock:
   `python3 hardware/cad/design_control.py lock --owner OWNER`.
   Never remove another owner's lock or expire it automatically.
2. Recheck live MAIN identity, latest/saved state and the lock's registry digest.
   Preserve every affected unsaved document. A changed baseline requires
   reconciliation; it must not be forced through the old acceptance.
3. Integrate and review a candidate in a separate document. Verify intended
   geometry and unrelated bodies, joints, appearances, placements and visibility,
   including hidden geometry. Avoid broad recomputation or silent mesh repair.
   Check printable solids and affected interfaces.
4. Export and integrity-check a fresh native MAIN backup before mutation.
   Recheck the baseline, apply only the reviewed scope to the existing lineage,
   and save with the acceptance/change description. Wait for cloud processing;
   verify the permanent file ID, new cloud version and saved state.
5. Export native and matching required geometry into a new ignored candidate
   directory. Verify native reimport, mesh geometry and source/frame provenance.
   Label partial downstream packages honestly; CAD acceptance may precede print
   preparation or guide updates.
6. Update compact public provenance with parent identity, before/after cloud
   versions, changed IDs/hashes, approval scope, validation and limitations.
   Keep detailed acceptance history and transaction backup locations in ignored
   local notes; do not link public inputs to them. Stage the complete
   selected current input set and any delivery record; validate their bindings before selecting
   them. Advance the registry last and regenerate CURRENT-DESIGN.md. Current
   checks remain mandatory when no delivery is selected.
7. Run `python3 hardware/cad/design_control.py check`. Record completion or a
   safe abort, then release your own lock:
   `python3 hardware/cad/design_control.py unlock --owner OWNER`.
   Commit the accepted files and necessary public provenance together after the relevant
   checks pass. Keep transaction backups until the saved selection is verified.

Keep a transaction checkpoint across interruptions; the registry alone cannot
explain a half-finished cloud save or file installation. If the cloud is newer
than the selected accepted revision, preserve it as an unreviewed candidate and
reconcile it. Do not infer acceptance from its existence. Inspect the owner and
actual state of a leftover lock before completing or abandoning a transaction.

## Portable helpers

`hardware/tools/cad/export.py` takes an explicit request with `cloud_file_id`,
`cloud_version`, `part_ids`, `include_hidden` and a new `output` directory.
`python3 hardware/tools/cad/export.py --validate-request REQUEST.json` checks the
request offline. Its `export(request)` adapter runs inside Fusion against an
already open, clean document; it does not save or mutate the design. This adapter
has offline validation tests but has not yet been qualified in live Fusion.
Native reimport, bed-frame export and design acceptance remain separate checks.

For local publication, mirror the intended repository paths in a new candidate
directory, including the new registry and its generated current-design summary.
Use `hardware/tools/cad/publish.py stage --candidate DIR --journal NEW_DIR
--owner OWNER --file PATH` with one `--file` per changed path; registry and summary
are required. Staging checks the resulting complete selection without changing
the checkout. With your promotion lock held, run `publish.py install --journal
DIR --owner OWNER`. It checks the baseline, preserves before/after bytes and
installs the registry last. An interruption leaves a marker that blocks current
checks; `publish.py recover --journal DIR --owner OWNER` restores the recorded
prior files only after ruling out conflicting edits. Keep the journal until the
accepted selection is committed and verified. None of these commands changes live
CAD or machinery.

## Recovery

Preserve questionable or interrupted state before repair. Restore the exact
native/export/project bytes from the recorded Git commit or tag, checking their
manifest hashes in a separate ignored recovery workspace. Verify the restored
selection before using it.

If MAIN needs restoration, restore the accepted geometry into the same permanent
cloud lineage as a **new cloud version**. Verify it and create a new recovery
acceptance record with that version. Preserve the previous accepted revision in
Git. File installation recovery must preserve the transaction's before/after evidence and
reconcile the registry with the verified complete set before work resumes.

## Handoff to printing and the guide

Record affected inputs and downstream disposition in the local work record;
maintain the reproducible public bindings and current limitations separately.
A native occurrence-transform change can affect assembly fit, service clearance,
kinematics, fastening and images even when STL bytes stay identical. Correcting
an export that omitted an already accepted placement is a representation repair;
verify that distinction against the native source.

Follow the [print procedure](../printing/current/README.md) for affected full
plates and the [guide procedure](../build-guide/README.md) for affected content.
The guide has a manual release checklist and is not pinned by the CAD registry or
delivery. Release the CAD lock after safe completion; do not hold it while waiting
for guide prose or a physical print.
