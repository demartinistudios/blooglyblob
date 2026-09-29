<a href="hardware/build-guide/README.md">
  <img src="hardware/build-guide/src/assets/robot-mark.svg" alt="BlooglyBlob — open the build guide" width="120" height="170">
</a>

# Blooglyblob

Blooglyblob is a conversational Raspberry Pi character with a microphone,
speaker, button, lights, and servos. One application runs on the Pi. The button
starts a conversation; OpenAI supplies cloud AI.

**Development prototype — not a validated build kit.** The design and guide are
still being reviewed. CAD-to-print agreement, assembly instructions and physical
qualification have open checks; review the [current status](docs/release/publication-inventory.md#current-readiness)
before buying parts, printing or operating hardware.

**Build and use at your own risk.** No safety or performance guarantees are made.
You are responsible for your assembly, testing and use. Children must work with
and use the robot under direct adult supervision. Read the
[safety and responsibility notice](hardware/SAFETY.md) before starting.

- [Set up the software: Raspberry Pi Imager → Make](docs/software/setup.md)
- [Update, diagnose, and repair](docs/software/maintenance.md)
- [Contribute and run checks](CONTRIBUTING.md)
- [Runtime architecture and behavior](docs/software/architecture.md)
- [Build guide: local preview and future hosting](hardware/build-guide/README.md)
- [Authoritative hardware design](hardware/cad/CURRENT-DESIGN.md)
- [Release preparation and remaining qualification](docs/release/checklist.md)
- [Publication contents and rights review](docs/release/publication-inventory.md)

The build guide lives in `hardware/build-guide/` as part of this repository. A normal
clone includes its sources and selected CAD/print inputs. Run `make guide-build`
to generate the preview pages and downloadable packages.

Run `make help` for commands. Provisioning is safe to rerun; application updates
preserve configuration and calibration and do not change system packages.
There is no desktop client, alternate AI provider, or wake-word setup.

Software cleanup and hardware-free tests do not establish physical kit readiness.
The [validation record](docs/software/validation.md) separates local tests,
deployment checks, and physical acceptance for the single application. Earlier
Pi 3B+ search and follow-up checks used the previous two-process runtime.
Microphone clipping, an intermittent ignored-follow-up report, full-application qualification,
reference Pi 3A+ qualification, and replacement audio remain open.
Public source availability does not certify the build instructions or hardware.
The [release checklist](docs/release/checklist.md) separates repository publication
from a validated build-kit release.

Original software, hardware designs and build materials are [MIT licensed](LICENSE).
See [license scope](LICENSING.md) for third-party exclusions and separate audio terms.
