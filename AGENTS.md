# Working in this repository

Use [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks. Run focused checks
while iterating and `make check` before handing off completed implementation
work; rerun affected checks after further edits. For physical design,
printing or guide work, start at [hardware/README.md](hardware/README.md), then
read the relevant area procedure before changing inputs. Keep hardware assets,
tools and records under `hardware/`; runtime device modules belong in
`blooglyblob/hardware/`. Do not recreate retired layouts or nested repositories.

Follow the checkout and branch selected for the task. Read
local workspace preferences in `.git/info/local-workspace.md` when present,
including any machine-specific desktop file-opening instructions. Do not switch
branches, create worktrees, stash, or discard others' work without the owner's
instruction. Agree ownership before overlapping edits; use explicit file lists
when staging or committing. Recheck repository and relevant live device state
before consequential operations.

## Communication and continuity

- Message only affected task owners when they need to act or change a decision:
  a completed handoff, blocking question, ownership conflict, or invalidated
  assumption. Flag urgent conflicts immediately.
- Batch routine updates into one actionable handoff. Keep progress and detailed
  evidence in current project records; do not send a play-by-play.
- Keep messages brief: what changed, the recipient's required action, and a link
  to the authoritative record. Avoid broadcasts, duplicate updates, status
  polling, and acknowledgment-only replies unless needed to unblock work.
- Read current records when resuming. Coordinate shared-file ownership before
  overlapping edits; silence does not grant approval or ownership.

At meaningful transitions, update the existing work record with objective,
accepted baseline, decisions/constraints, owned files, completed checks and
links, blockers, and next action. Read that checkpoint after compaction or a
handoff. Keep working notes, review diaries, personal printer operations, plans
and investigations in ignored local locations: `hardware/.work/`,
`hardware/records/`, `hardware/printing/operations/`, `docs/plans/` and
`docs/investigations/`. Publish only maintained contributor/user guidance and
compact technical provenance required to reproduce the current inputs. Do not
link public files to private notes or create transcript copies or competing status
files. Ignored files need a separate private backup; Git does not preserve them.

## Software invariants

The runtime is one OpenAI-only Pi application, `python -m blooglyblob`, managed
by `blooglyblob.service` and activated by button. Preserve hardware-free imports
and tests, generation fencing, audio ownership locks, playback drain barriers,
and bounded session cleanup; add focused regression coverage when changing
these boundaries. See [runtime architecture](docs/software/architecture.md).
Do not restore remote-brain abstractions, retired providers, wake-word code,
desktop clients, automatic rollback, or whole-machine process killing.

Never source credential files as shell code or print credentials. Device motion,
physical tests and real API calls require explicit authorization; they are not
contributor checks. Follow [setup](docs/software/setup.md) and
[maintenance](docs/software/maintenance.md) for current device procedures.
Historical commands and completed plans are not current instructions or a new
work queue. For software/public-release work, start at the
[publication inventory](docs/release/publication-inventory.md).
