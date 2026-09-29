# Publication and validated-release checks

Use the [publication inventory](publication-inventory.md) for current findings and
[license scope](../../LICENSING.md) for grants and exceptions. A public development
repository and a validated build kit are different milestones. The owner approves
the visibility change; source availability does not certify hardware readiness.

## Public development repository

- Stage only the reviewed, explicitly named public files and run
  `make publication-check`; this checks the staged Git index, not unstaged edits.
  It is also included in `make check`.
- Review the exact source selection and intended Git history for credentials,
  private information and redistribution rights. Include native metadata, images,
  packaged downloads and any superseded GitHub commits still retrievable by SHA.
  Review GitHub Actions logs/artifacts and other hosted content too. A history
  rewrite alone does not remove server-side cached objects.
- Exclude local credentials, calibration, machine state, experiments, caches and
  environments. Keep publisher documents as external links, with no previous
  copies accessible from the public repository. Rotate confirmed exposed secrets.
- Include the owner's MIT grant, third-party exclusions, CC0 sound-effect notice
  and [separate soundtrack notice](../../LICENSING.md#project-soundtrack-separate-terms).
  Soundtrack inclusion does not grant an unrestricted music license.
- Confirm the GitHub destination, selected refs and public commit identities.
  Use the agreed clean history and maintainer business email. Do not change
  visibility, rewrite history or publish to another destination without approval.
- State prominently that this is a development prototype with an unverified build
  guide. Link current limitations; do not mark pending hardware reviews as passed.
- Verify contributor checks for the intended source, plus focused checks after
  documentation changes. Keep the local guide preview available independently of
  release qualification, using the [guide procedure](../../hardware/build-guide/README.md#build-and-preview).
- Resolve the recorded publication blockers, then obtain the owner's approval to
  change visibility. Recheck the remote state immediately before that action.

## Hosted development guide

Website deployment and hardware qualification are separate decisions. The Pages
workflow requires current-input integrity, a successful guide build and browser
checks. Pending kit reviews remain visible in its job summary; they are not
converted into approvals and do not alone prevent website deployment.

- Apply the source/privacy/rights checks above to everything the site distributes.
- Run `python3 scripts/check_pages.py` and `make guide-browser`. The first command
  uses the existing offline validator and reports outstanding reviews and kit
  delivery selection. Input errors or an invalid validator result fail the job.
  The second builds the guide and checks routes, links, images and interactions.
- Inspect the outstanding reviews before making readiness claims. Passing website
  checks does not prove geometry equivalence, connector fit or physical assembly.
- Obtain the owner's authorization to publish. Verify the successful deployment
  and public URL before reporting that the site is live.

The [guide procedure](../../hardware/build-guide/README.md#publication-readiness)
and [workflow](../../.github/workflows/guide-pages.yml) define website checks.

## Validated build kit

The following remain required before claiming a synchronized, qualified kit.
They do not need to be complete merely to share development source or host the
development guide.

- From a fresh source checkout, run `make dev-setup`, `make guide-setup` and
  `make check` as documented in [contributing](../../CONTRIBUTING.md). Verify
  installed-package resources and downloadable CAD/print inputs too.
- Run `python3 hardware/tools/validation/check.py --publication` and resolve all
  pending source comparisons, stale review evidence and unsupported commands.
  Review affected assembly views, instructions, supply/fastener allocations and
  downloads against the same accepted inputs. Automated checks do not prove fit.
- Complete a fresh Imager-to-Make installation on the reference Pi with a custom
  hostname/user, repeat provisioning, reboot and exercise update failure/repair.
  Record board, image, Python, dependency versions and release commit.
- Complete the [physical and acoustic qualification](../software/validation.md#physical-qualification)
  with current hardware, then repeat relevant checks on replacement audio before
  making replacement-kit claims. Device tests require explicit authorization.
- Have a fresh builder follow the software and hardware guide together. Record
  unresolved fit, strength, wiring and optical results honestly.
- Review the exact generated build-kit contents and metadata. Before distributing
  a prebuilt environment or image, assess its dependency licenses and notices.
- Obtain the owner's approval for the qualified release. A successful
  preview, slice or print does not establish physical qualification.
