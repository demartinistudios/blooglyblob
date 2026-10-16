# Publication inventory

For agents preparing publication: this is a map of the public
files, their provenance and license coverage. Use the [publication checklist](checklist.md)
for actions before publishing. Builders should start with the
[build guide](https://demartinistudios.github.io/blooglyblob/) and
[safety notice](../../hardware/SAFETY.md).

DeMartini Studios LLC publishes free files and instructions, with no kits,
assembled robots, hosted AI service or promised support. See
[project status and support](../../hardware/SAFETY.md#project-status-and-support).

## Public selection

| Area | Maintained contents |
| --- | --- |
| Software | Application, scripts, configuration examples, requirements, tests and service definitions; [contributor setup](../../CONTRIBUTING.md) |
| Hardware | Native CAD and exports selected by the [registry](../../hardware/cad/design-control/registry.json), current editable print projects, catalogs, assembly requirements and necessary provenance |
| Guide | One authored `hardware/build-guide/src/` tree; `make guide-build` derives ignored pages and downloads from maintained inputs |
| References | [Component-reference catalog](../../hardware/references/community-20260925/catalog.json) with external publisher links and original measured photographs |
| Media | Assets, source identity, hashes and rights in [asset-manifest.json](asset-manifest.json) |

Personal printer operations, detailed work records, plans and investigations stay
local in ignored folders. Keep credentials, calibration, machine configuration,
experiments, generated guide output and dependency environments out of the public
selection. Public builds must work without those files. Follow the
[hardware retention policy](../../hardware/README.md#retention).

## Readiness and validation scope

The author's one-prototype experience and its limits are described in
[Build experience and limitations](../../hardware/SAFETY.md#build-experience-and-limitations).

For contributors, [software validation](../software/validation.md),
[CAD notes](../../hardware/cad/CURRENT-NOTES.md),
[print guidance](../../hardware/printing/current/README.md) and the
[guide review record](../../hardware/build-guide/REVIEW.md) explain technical
constraints and the scope of recorded evidence. Current print-source comparisons
are verified. The guide may contain errors or omissions; neither file checks nor
website deployment establish physical safety. The
[checklist](checklist.md) explains the separate website and optional delivery checks.

## Privacy and metadata

Publication review includes earlier Git versions and metadata embedded in CAD,
print projects and images, not just visible text. Follow the
[privacy checks](checklist.md#public-development-repository) before publishing.

The [privacy proof](../../hardware/printing/recipes/project-privacy.json) records
removal of Bambu `DesignerUserId` metadata. Packaging rejects nonempty values;
that check is not a general privacy audit.

## License coverage

[LICENSING.md](../../LICENSING.md) defines the license grants and every
exception, and the guide footer credits the third-party material the guide
uses. Publisher reference documents are linked externally, not bundled with the
source or generated guide. Original project templates remain included.

### Dance song

The project soundtrack and its beat and light data are included under the
[separate soundtrack notice](../../LICENSING.md#project-soundtrack-separate-terms),
not MIT or CC0. The song was generated using ElevenLabs;
`scripts/analyze_beats.py` and `scripts/analyze_song_lights.py` derive the beat
and light data from it. Keep the notice with project packages and Pi
payloads. Source identity and hashes are in
[asset-manifest.json](asset-manifest.json); private licensing correspondence
and billing records are not part of the public repository.

## Dependency notices

Original-code licensing does not relicense dependencies. The source package and
Pi payload install dependencies separately rather than bundling a Python
environment. A prebuilt image requires a review of its exact binaries, embedded
libraries, notices and corresponding-source obligations.

Known notice considerations for the inspected dependency versions include:

- SoXR/libsoxr: LGPL-2.1-or-later in the inspected 1.1.0 distribution.
- Certifi and development dependency pathspec: MPL-2.0.
- `ring-doorbell`, used only by the optional Ring setup helper: LGPL-3.0.
  Optional beat-analysis tools need their own review and remain outside the Pi
  runtime environment.
- rpi-ws281x 5.0.0: BSD-2-Clause in its source license texts despite MIT package metadata.
- Selected pigpiod v79 source: Unlicense; retain its supplied notice.

Data from TMDB, JustWatch (through TMDB) and Watchmode, used by the optional
streaming feature, requires attribution; the
[README](../../README.md#safety-and-license) gives it.

This list does not exhaustively cover Pi OS or all ARM and optional helper
binaries. Review resolved versions when redistributing a prebuilt environment.
