# Contributing

Read [AGENTS.md](AGENTS.md) before changing this checkout. For CAD, print recipes
or assembly-guide changes, follow the [hardware workflow](hardware/README.md).
Contributors and forks can run its offline checks and propose changes without
maintainer Fusion access. Participation follows the
[code of conduct](CODE_OF_CONDUCT.md).

## Setup and checks

Use Python 3.12 or 3.13, Node.js 22 or newer with npm, Git and Make. From the
repository root, choose an installed Python explicitly:

```sh
make dev-setup HOST_PYTHON=python3.12
make guide-setup
make check
```

Setup downloads dependencies. On Linux, `make guide-setup GUIDE_SYSTEM_DEPS=1`
also installs Chromium's system packages and may require administrator access;
use it only when you intend that installation. Ordinary checks never install
packages, require credentials, contact a device or make model API calls.

`make check` runs the publication-boundary check; software formatting, lint,
types and tests; hardware tooling tests and invariants; then the guide build and
browser checks. The browser check
uses its own temporary server and browser context. A passing check does not
approve hardware promotion, physical operation or public release.

| When | What to run |
| --- | --- |
| First setup or dependencies change | The setup commands above |
| While editing | Format owned files and run focused checks/tests |
| Before a commit, if opted in | Git runs staged Python formatting and lint checks |
| Before handing off an implementation for review | `make check`; rerun affected checks after subsequent edits |
| Push or pull request | CI runs the same checks, Python 3.12/3.13 tests, and installed-wheel validation |

Questions and planning do not require checks. For prose-only edits, use relevant
link/documentation checks locally; CI still checks the complete repository.

Use `make help` to discover commands. `make dev-check` covers software alone;
`make hardware-test` and `make hardware-check` cover hardware tools/invariants.
`make dev-test`, `make dev-lint`, `make dev-typecheck` and `make dev-format-check`
run individual software checks. For one test file:

```sh
.venv/bin/python -m pytest tests/test_runtime_configuration.py -q
```

`make dev-format` rewrites software formatting; checks and CI never do. In a
shared checkout, format only your owned files with
`.venv/bin/python -m ruff format path/to/file.py`. Hardware-control modules under
`blooglyblob/hardware/` retain their existing formatter exclusion. Ruff checks
Python in `blooglyblob/`, `scripts/` and `tests/`; type checking also covers the
installation scripts. Domain tools keep their existing validation procedures.

`DEV_PYTHON` selects the development environment for checks; `HOST_PYTHON` selects
the Python used for setup and standard-library hardware tools. Commands are
orchestrated in `Makefile`, implemented in `scripts/check.sh` and domain tools,
and configured in `pyproject.toml`.

### Optional commit hook

After setup, run `make dev-install-hook` to opt in for this checkout. Installation
preserves existing hooks and refuses to replace a configured `core.hooksPath`.
If you already manage hooks, invoke the development Python with
`scripts/pre_commit.py check` from your existing pre-commit hook instead.

The hook checks staged Python and the staged root Ruff configuration, including
partially staged files. It never fixes, stages or stashes changes, installs
packages or runs tests. Fix failures, stage the intended changes, then retry.
To uninstall the generated hook, remove only its `pre-commit` file at the path
printed during installation, after confirming it still contains the generated
wrapper. There is no automatic pre-push or agent end-of-turn check.

### Dependency updates

`requirements-dev.txt` declares development tools and includes runtime inputs and
shared Pi constraints. `requirements/dev.txt` pins the remaining development
resolution. `make dev-setup` installs both, without isolated build downloads.
The guide uses its committed npm lockfile. The Pi additionally installs
`requirements/hardware.txt`; host checks do not qualify that device environment.

To change development dependencies, edit the direct pins if needed, then run:

```sh
python3.12 scripts/update_dev_constraints.py
```

This explicit network operation uses pip 25.3 in a disposable environment,
resolves the declared inputs and regenerates development-only constraints.
It does not freeze your everyday environment or rewrite the shared Pi pins.
Review the diff and validate fresh Python 3.12/3.13 environments with
`pip check` and contributor checks on macOS and Linux. Keep dependency updates
separate from unrelated behavior changes. New dependencies need a retained use.

### CI and coverage

CI has three stable checks: `Software (3.12)`, `Software (3.13)` and
`Hardware and guide`. When supported by the repository's GitHub settings, require
all three on the default branch, with the branch up to date before merging.
Workflow files alone do not enforce merge protection. Maintainers configure this
under Settings → Rules → Rulesets or branch protection and verify the effective
rules against actual emitted check names. Availability depends on repository
visibility and the account plan; do not change either merely to enable a check.

The Python 3.12 CI test run collects informational branch coverage once, with a
report retained for seven days. Run `make dev-coverage` locally when needed;
it runs the tests and writes ignored coverage output. There is no coverage
percentage gate. Inspect missing branches and behavioral assertions rather than
using the percentage as proof of correctness.

## Working on a change

Read current sources and relevant procedures, state the intended behavior, and
plan when the change warrants it. Implement a focused slice, verify it, and
record checks and remaining limits in the existing work record or review.
Preserve the software invariants in [AGENTS.md](AGENTS.md).

- Fix meaningful defects with focused regression checks where practical; encode
  recurring failures in existing tests or validators.
- Explain any disabled checks, broadened exclusions or lowered thresholds in the
  review. Do not weaken checks just to obtain a passing result.

## Where changes belong

| Area | Source and responsibility |
| --- | --- |
| Application | `blooglyblob/application.py` owns startup/shutdown; `blooglyblob/conversation.py` coordinates sessions and activities |
| Audio | `blooglyblob/audio/` owns capture, one speaker writer, mixing and resampling; `blooglyblob/media.py` coordinates completion |
| Hardware control software | `blooglyblob/hardware/` owns button, lights, servos, local media and diagnostics |
| AI and tools | `blooglyblob/ai/` owns OpenAI adapters; `blooglyblob/tools/` owns validated tool execution and integrations |
| Installation | `scripts/deploy.py` runs host-side SSH operations; `scripts/device_install.py` installs on the Pi; `systemd/` defines the application service and GPIO daemon |
| Runtime resources | `tool_configs/`, `blooglyblob/ai/` persona/voice JSON files, and approved files in `songs/` and `sounds/` |
| Regression checks | `tests/` and `.github/workflows/ci.yml`; Pi diagnostics remain explicit operator actions |

Shared test doubles and fixtures live in `tests/support/`. Import them from that
package rather than from another test suite. Keep dependency replacement scoped
to a fixture or inject the collaborator; test collection must not replace real
dependency modules globally.

The central application, conversation, and media modules have checked type
contracts. Use type-only imports when a collaborator would otherwise load device
or optional integration code during import. Preserve lifecycle guards when
clarifying types.

Read [runtime behavior](docs/software/architecture.md) before changing session or audio
ownership. The current audio lifecycle, generation checks, and physical playback
completion protect interruption and transitions between conversation,
dance, and alerts. Old investigations describe earlier implementations; consult
the current source and tests before applying their instructions.

## Identity and private data

Keep credentials in ignored `.env`, `.env.*`, or `*.env` files. Public
`.env.example` and `*.env.example` templates remain visible to Git and must
contain placeholders only. A custom credential path with another filename
needs its own ignore rule; ignore rules do not untrack previously committed files.

Working notes and personal activity stay local in ignored `hardware/.work/`,
`hardware/records/`, `hardware/printing/operations/`, `docs/plans/` and
`docs/investigations/`. Back these up privately when needed. Public documentation
should describe the current project; retain only the concise provenance needed
to reproduce inputs and understand limitations. Public builds and links must not
depend on ignored files. Check the intended public file selection before staging;
never force-add a private record to satisfy a build dependency.

`make publication-check` inspects the staged Git index, including private paths,
credential patterns and packaged metadata. Stage only reviewed, explicitly named
public files before running it; it does not inspect unstaged edits or authorize a
push. The same check is included in `make check`. Keep required provenance in a
maintained public location rather than exempting private records from the check.

The maintainer's repository email is `anthony@demartinistudios.com`. Configure
maintainer checkouts with:

```sh
git config --local user.email anthony@demartinistudios.com
```

This affects future commits only. Other contributors
should use their own chosen public or GitHub-provided private commit address.
The build guide shares this repository's Git configuration.

## Optional model comparison

`scripts/evaluate_openai_models.py` compares its two supported OpenAI models on
eight built-in examples such as timers, movement, dance, and clarification.
Robot actions are mocked, but model requests are real: **bring your own OpenAI
API key and pay for the input/output tokens consumed by your account.** This
helper is optional and separate from the offline developer checks above.

Use the development environment created by `make dev-setup`. Supply
`OPENAI_API_KEY` through your environment, or set `BLOOGLYBLOB_ENV_FILE` to
your ignored runtime file, such as `config/app.env`. Exported values take
precedence. The helper does not automatically load a file or the root deployment
`.env`. Keep keys out of source and committed results.

From the repository root, inspect the available model choices without API calls:

```sh
.venv/bin/python -m scripts.evaluate_openai_models --help
```

To deliberately run a small, billable comparison:

```sh
.venv/bin/python -m scripts.evaluate_openai_models \
  --cases 1 --output /tmp/blooglyblob-model-comparison.json
```

`--cases` selects the first 1–8 examples **per model**; the default runs all eight
against both models (`gpt-5.6-luna` and `gpt-5.6-terra`). Use `--models` to select
a subset from the choices shown by `--help`. Your account needs access to each selected model. A case can
make several requests, so the case count is not a token or dollar spending cap.

The JSON records expected/observed tool calls, scores, elapsed time, token usage,
and error classes. An existing output file is overwritten. Inspect each result's
`success` and `error_class`: writing a report does not mean every case passed.
Usage covers the Responses requests, not voice sessions or speech generation;
the helper does not calculate a price. Hardware actions and integrations are
mocked and hosted search is disabled, so results do not measure voice quality,
Pi latency, or full conversation behavior.

## Licensing contributions

By submitting a contribution, you confirm that you have the right to submit it
and agree that your original contributions are licensed under the project's
[MIT license](LICENSE).
[License scope](LICENSING.md) identifies coverage and exceptions.

Add third-party material, such as models, images, fonts, audio or documents,
only if its terms allow redistribution, and include its license text. Record
media in the [release asset inventory](docs/release/asset-manifest.json); for
other files, such as CAD models, record the source and terms in a README beside
them. List the material as an exception in [LICENSING.md](LICENSING.md).

## Optional song authoring

The [beat-analysis helper](docs/software/beat-analysis.md) estimates song tempo
and beat timestamps for dance synchronization. Its separate setup and commands
run on your computer; it is not required for normal development or Pi operation.

`make pi-run` runs the application in the foreground on the Pi and restores
the service’s prior active state after it exits and releases its devices.
Ownership-uncertain exit status 73 leaves the service stopped for inspection. A
conversation makes real, billable API requests. Hardware-free development uses
the tests above; the complete application requires the Pi drivers and devices.

Do not commit secrets or personal runtime state. Public publication requires
the separate [release checklist](docs/release/checklist.md). The
[publication inventory](docs/release/publication-inventory.md) records current
contents, rights questions and remaining readiness gates.
