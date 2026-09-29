"""Gate Pages on current-input integrity and report separate kit-release reviews."""

import html
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
# Required report sections from hardware/tools/guide/consistency.py. This checks
# report completeness; the underlying validator still owns review decisions.
GUIDE_SURFACES = {
    "instructions",
    "part-supply-cards",
    "print-cards-downloads",
    "assembly-visuals",
    "diagrams-templates",
    "references",
    "software-commands",
    "progress-and-navigation",
}


def validate_report(report):
    if not isinstance(report, dict) or type(report.get("ok")) is not bool:
        raise ValueError("Validator returned an invalid status")
    for key in ("errors", "blockers"):
        values = report.get(key)
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
            raise ValueError(f"Validator returned invalid {key}")
    if not isinstance(report.get("stages"), dict):
        raise ValueError("Validator returned invalid stages")
    if report["ok"] != (not report["errors"]):
        raise ValueError("Validator status disagrees with its input errors")
    if report["ok"]:
        validate_success_stages(report)
    return report


def validate_success_stages(report):
    stages = report["stages"]
    for name in ("cad", "render-inputs", "printing", "guide"):
        if not isinstance(stages.get(name), dict) or not stages[name]:
            raise ValueError(f"Validator success report is missing stage: {name}")
    for name in ("cad", "render-inputs"):
        if stages[name].get("status") != "verified":
            raise ValueError(f"Validator success report has unverified {name}")
    printing = stages["printing"]
    if printing.get("immutable_recipe_identity") != "verified":
        raise ValueError("Validator success report has unverified recipe identity")
    pending = printing.get("publication_blockers")
    if not isinstance(pending, list) or any(not isinstance(x, str) for x in pending):
        raise ValueError("Validator printing stage has invalid blockers")
    if printing.get("independent_source_geometry") != (
        "pending" if pending else "verified"
    ):
        raise ValueError("Validator geometry status disagrees with pending reviews")
    expected = list(pending)
    if not GUIDE_SURFACES.issubset(stages["guide"]):
        raise ValueError("Validator guide stage is missing required review surfaces")
    for surface, review in stages["guide"].items():
        if (
            not isinstance(review, dict)
            or review.get("status") not in ("verified", "pending", "blocked")
            or not isinstance(review.get("reason"), str)
        ):
            raise ValueError(f"Validator guide stage has invalid review: {surface}")
        if review["status"] != "verified":
            expected.append(f"{surface}: {review['status']} — {review['reason']}")
    if report["blockers"] != expected:
        raise ValueError("Validator review summary disagrees with its stage results")


def details(title, messages):
    return (
        f"<details><summary>{title}</summary>\n\n<pre>"
        + html.escape("\n".join(messages))
        + "</pre>\n\n</details>\n"
    )


def main():
    errors = []
    blockers = []
    review_status = "Release-review status unavailable."
    delivery_status = "Kit delivery status unavailable."
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "hardware/tools/validation/check.py"),
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        report = validate_report(json.loads(completed.stdout))
        errors.extend(report["errors"])
        blockers = report["blockers"]
        review_status = f"{len(blockers)} outstanding release reviews."
        if completed.returncode != (0 if report["ok"] else 1):
            errors.append(f"Validator exited unexpectedly: {completed.returncode}")
        registry = json.loads(
            (ROOT / "hardware/cad/design-control/registry.json").read_text()
        )
        if not isinstance(registry, dict) or "delivery" not in registry:
            raise ValueError("Registry is missing delivery-selection status")
        if registry["delivery"] is None:
            delivery_status = "No kit delivery selected."
        elif isinstance(registry["delivery"], dict) and registry["delivery"]:
            delivery_status = "Kit delivery selected; selection is not qualification."
        else:
            raise ValueError("Registry has an invalid delivery-selection status")
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"Could not complete Pages input checks: {exc}")

    summary = (
        "## Pages input checks\n\n"
        f"**Input integrity: {'FAIL' if errors else 'PASS'}**\n\n"
        f"{review_status} {delivery_status}\n\n"
        "Pending reviews do not block website deployment. Passing this check does "
        "not establish hardware qualification; the guide build and browser checks "
        "must also pass before deployment.\n\n"
        "For the strict kit-release gate, run "
        "`python hardware/tools/validation/check.py --publication`.\n\n"
    )
    if errors:
        summary += details("Input errors — deployment blocked", errors)
    if blockers:
        summary += details("Outstanding release reviews — unchanged", blockers)
    print(summary)
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        try:
            with Path(summary_path).open("a", encoding="utf-8") as output:
                output.write(summary)
        except OSError as exc:
            print(f"Could not write Pages check summary: {exc}", file=sys.stderr)
            return 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
