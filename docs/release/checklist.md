# Publication checks

For agents publishing repository files or the website. The
[publication inventory](publication-inventory.md) maps the public contents;
[license scope](../../LICENSING.md) defines grants and exceptions. Publishing
files does not certify a physical build.

## Public development repository

- Stage only reviewed, explicitly named files and run `make publication-check`.
  It checks the staged Git index, not unstaged edits or all historical versions;
  it also runs within `make check`.
- Review the selected files, Git history, downloads, images and embedded CAD/print
  metadata for credentials, private information and redistribution rights.
  A clean working tree only means no uncommitted changes: earlier commits can
  still contain removed material. Check retrievable older GitHub commits,
  Actions logs/artifacts and other hosted copies; rewriting history alone does
  not remove server-side cached objects.
- Exclude credentials, calibration, machine state, experiments, caches and
  environments. Keep private legacy branches/tags out of public pushes. Link to
  publisher reference documents rather than bundling copies, including in old
  public commits. Rotate any confirmed exposed credential; deleting it does not
  invalidate it.
- Bambu projects/downloads must have no nonempty `DesignerUserId`; this narrow
  packaging check does not audit all metadata. Native CAD can contain application
  resource paths. Review them without arbitrary byte edits that could corrupt the
  file or invalidate accepted hashes.
- Include `LICENSE`, `LICENSING.md` and `LICENSES/`, including the Adafruit MIT,
  CC0 sound-effect and [separate soundtrack notices](../../LICENSING.md#project-soundtrack-separate-terms).
  Check guide footer credits and each print ZIP's license and safety notices.
- Confirm the destination, selected branches/tags and commit identities. Use the
  agreed public history and maintainer business email. Visibility changes,
  history rewrites and other publication destinations require owner approval;
  resolve recorded blockers and recheck remote state before the authorized action.
- Describe prototype experience, testing limits and the absence of promised
  support or future validation accurately. Link the [safety notice](../../hardware/SAFETY.md);
  describe only the evidence actually collected. Run contributor checks for the
  intended source and affected checks after further edits.

## Hosted development guide

The Pages workflow requires current-input integrity, a successful guide build and
browser checks. Separate print-input reviews appear in its job summary and do
not alone block website deployment.

- Apply the source, privacy and rights checks above to everything the site distributes.
- Run `python3 scripts/check_pages.py` and `make guide-browser`. The first reports
  outstanding print-input reviews and optional delivery selection; input errors or invalid
  validator results fail. The second builds the guide and checks routes, links,
  images and interactions.
- Inspect any outstanding print-input reviews before making readiness claims. Passing website
  checks does not prove connector fit or physical assembly.
- Obtain authorization to publish, then verify the successful deployment and
  public URL before reporting that the site is live.

See the [guide procedure](../../hardware/build-guide/README.md#publication-readiness)
and [workflow](../../.github/workflows/guide-pages.yml).

<a id="validated-build-kit"></a>

## Optional delivery snapshots and stronger claims

A selected delivery is an exact-file release snapshot used by the existing tools.
It does not mean the project supplies kits or that a build is certified. No
snapshot or further testing is promised. If preparing one or making a stronger
compatibility or performance claim, collect evidence for that specific scope:

- From a fresh checkout, run `make dev-setup`, `make guide-setup` and `make check`
  following [CONTRIBUTING](../../CONTRIBUTING.md). Check installed-package resources
  and downloadable CAD/print inputs.
- For a selected snapshot, run `python3 hardware/tools/validation/check.py --publication`.
  This strict check requires a selected delivery and resolved print-input reviews. Resolve
  any pending source comparison, stale evidence or unsupported command. Review
  views, instructions, supply/fastener allocations and downloads against the same
  inputs. Passing does not certify fit or safety.
- Before claiming a freshly reproduced installation, exercise Imager-to-Make
  setup on the reference Pi with a custom hostname/user, repeat provisioning,
  reboot and update failure/repair. Record board, image, Python/dependency
  versions and source revision. Device tests require explicit authorization.
- For measured device behavior, choose relevant [optional evaluation methods](../software/validation.md#optional-device-evaluation).
  Replacement-audio claims need checks on that replacement. A fresh builder's
  end-to-end guide review can add evidence; record unresolved fit, strength,
  wiring and optical observations rather than inferring success.
- Review the exact snapshot contents and metadata. Before redistributing a prebuilt
  environment or image, assess its dependency licenses and required notices.
- Obtain owner approval for publication and describe only the evidence actually
  collected. A preview, slice or successful print does not certify the device.
