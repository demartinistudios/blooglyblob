# Hardware

For assembly, open the [build guide preview](build-guide/README.md#build-and-preview).
Website deployment and physical qualification are separate checks. For contributions, this page
connects the three area procedures:
[CAD](cad/DESIGN-WORKFLOW.md), [printing](printing/current/README.md), and
[guide authoring](build-guide/README.md). A contributor or fork can inspect the
current inputs, build the guide and propose changes without maintainer credentials
or Fusion MAIN access. An authorized maintainer performs upstream CAD promotion.

## Start from a fresh checkout

Use Python 3.12 or 3.13 and run these commands from the repository root. These
offline commands use only the Python standard library; the full
[development setup](../CONTRIBUTING.md) is needed for application work:

```sh
make hardware-check
make guide-build
```

If `python3` selects another version, add `HOST_PYTHON=python3.12` to each Make
command.

The first command checks offline invariants. Outstanding publication reviews are
separate: use `python3 hardware/tools/validation/check.py --publication` to inspect
them. The second
builds a local preview; success does not authorize publication. Neither requires
Fusion, Bambu Studio, scratch outputs, credentials or
physical devices. Browser verification and optional authoring dependencies are
in the [guide procedure](build-guide/README.md).

## Sources of truth

| Information | Maintained source |
| --- | --- |
| Accepted CAD identity and exact cloud version | [Registry](cad/design-control/registry.json); [current design](cad/CURRENT-DESIGN.md) is its generated summary |
| Required native and geometry exports | [Current CAD inputs](cad/current/), selected and hash-checked by the registry's input lock |
| Part identity and dependencies | [Part catalog](catalog/parts.json) |
| Editable print projects and process | [Current print set](printing/current/README.md) and [recipe locks](printing/recipes/projects.json) |
| Installed hardware and electrical allocations | [Hardware allocations](assembly/hardware.json) and [electrical tables](assembly/electrical.json) |
| Current technical limitations | [CAD notes](cad/CURRENT-NOTES.md), [print procedure](printing/current/README.md), and [guide review](build-guide/REVIEW.md) |
| Purchased supply specifications | [Supply catalog](catalog/supplies.json); guide cards add presentation and links |
| Component references | [Reference catalog](references/community-20260925/catalog.json) linking to publisher documents |
| Assembly instructions | [Guide source](build-guide/src/), independent of CAD release selection |

Everything for the physical character belongs under `hardware/`, including
references, illustrations, tools and records. Software and repository-wide docs
belong under `docs/`; Pi device-control modules remain in `blooglyblob/hardware/`.

## One process, with separate stages

One person can perform all stages, or several owners can hand them off using the
same records and checks. Agree ownership before editing shared files.

1. Record the intent, accepted baseline, expected affected parts/interfaces and
   acceptance criteria in a unique ignored experiment run. Work in a separate
   CAD document; render or print trials only within the authorized scope.
2. Review the candidate's evidence and limitations. An authorized owner promotes
   only the accepted scope using the [CAD procedure](cad/DESIGN-WORKFLOW.md).
3. Identify affected geometry, placements, hardware, material/process, electrical
   and software dependencies. Record each downstream stage as `pending`,
   `blocked` or `verified` against its exact inputs. An unmapped impact needs
   review; a new global revision alone does not require rebuilding every output.
4. Update or verify affected [print recipes](printing/current/README.md) and
   [guide surfaces](build-guide/README.md). Record changed, reused and reviewed
   outputs with concise public evidence in the current review/provenance files;
   keep the detailed work record private.
5. Run offline checks, guide build and browser verification; review the assembly
   meaning and visuals before claiming a synchronized public build kit.

CAD may be accepted while printing or guide work remains pending. A qualified
build-kit release requires those dependencies and blockers to be resolved.
The development source and guide can be shared with their limitations stated;
see the [release checks](../docs/release/checklist.md).
Digital validation, machine completion, usable stock and physical fit/strength/
optical qualification are distinct evidence. A passing slice does not establish
physical qualification; printing and deployment are separate authorized actions.

## Retention

Keep one current required set of native CAD, geometry exports and editable print
inputs in Git, with compact provenance, exact hashes and current limitations.
A CAD checkpoint may precede print or guide acceptance. Guide prose changes need
no CAD release.

Keep experiments, candidate slices, renders and transaction backups in ignored
`hardware/.work/<category>/<run-id>/`. Existing detailed work records remain local
under ignored `hardware/records/`; printer queues, stock and job history belong in
ignored `hardware/printing/operations/`. Record owner, baseline, purpose, useful
results and next action there. Publish maintained inputs and necessary technical
conclusions, not work diaries or entire run trees.

Before cleanup, confirm ownership, identify all consumers and privately back up
unique useful work. Git does not protect ignored or uncommitted files. Keep active
work until its owner releases it; never make a public build depend on local notes.
