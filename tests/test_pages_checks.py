"""Pages blocks broken inputs without pretending pending kit reviews passed."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    script = tmp_path / "scripts/check_pages.py"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "scripts/check_pages.py", script)
    registry = tmp_path / "hardware/cad/design-control/registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"delivery": None}))
    validator = tmp_path / "hardware/tools/validation/check.py"
    validator.parent.mkdir(parents=True)
    return tmp_path


def run_check(project, report, exit_code=0, raw=False):
    output = report if raw else json.dumps(report)
    (project / "hardware/tools/validation/check.py").write_text(
        "import sys\n"
        "assert sys.argv[1:] == ['--json']\n"
        f"print({output!r})\nraise SystemExit({exit_code})\n"
    )
    summary = project / "summary.md"
    result = subprocess.run(
        [sys.executable, str(project / "scripts/check_pages.py")],
        cwd=project,
        env={**os.environ, "GITHUB_STEP_SUMMARY": str(summary)},
        capture_output=True,
        text=True,
    )
    return result, summary.read_text()


def report(**changes):
    blockers = changes.get("blockers", [])
    return {
        "ok": True,
        "errors": [],
        "blockers": [],
        "stages": {
            "cad": {"status": "verified"},
            "render-inputs": {"status": "verified"},
            "printing": {
                "immutable_recipe_identity": "verified",
                "independent_source_geometry": "pending" if blockers else "verified",
                "publication_blockers": blockers,
            },
            "guide": {
                surface: {"status": "verified", "reason": "Reviewed"}
                for surface in (
                    "instructions",
                    "part-supply-cards",
                    "print-cards-downloads",
                    "assembly-visuals",
                    "diagrams-templates",
                    "references",
                    "software-commands",
                    "progress-and-navigation",
                )
            },
        },
        **changes,
    }


def test_pending_reviews_pass_without_becoming_approvals(project):
    result, summary = run_check(
        project, report(blockers=["Geometry comparison pending", "USB fit unconfirmed"])
    )
    assert result.returncode == 0, result.stderr
    assert "Input integrity: PASS" in summary
    assert "2 outstanding release reviews" in summary
    assert "Geometry comparison pending" in summary
    assert "USB fit unconfirmed" in summary
    assert "No kit delivery selected" in summary
    assert "does not establish hardware qualification" in summary
    assert summary in result.stdout


def test_actual_input_errors_block_pages(project):
    result, summary = run_check(
        project, report(ok=False, errors=["Current STL hash mismatch"]), exit_code=1
    )
    assert result.returncode == 1
    assert "Input integrity: FAIL" in summary
    assert "Current STL hash mismatch" in summary


@pytest.mark.parametrize(
    ("payload", "exit_code"),
    [
        ("Traceback: validator crashed", 1),
        ("not JSON", 0),
        ("[]", 0),
        ("{}", 0),
        (json.dumps(report(ok="yes")), 0),
        (json.dumps(report(blockers=[{}])), 0),
        (json.dumps(report(stages=[])), 0),
        (json.dumps(report(stages={})), 0),
        (json.dumps(report()), 1),
        (json.dumps(report(ok=False)), 0),
        (json.dumps(report(errors=["broken input"])), 0),
    ],
)
def test_invalid_or_inconsistent_validator_results_fail(project, payload, exit_code):
    result, summary = run_check(project, payload, exit_code, raw=True)
    assert result.returncode == 1
    assert "Input integrity: FAIL" in summary


def test_selected_delivery_does_not_claim_qualification(project):
    (project / "hardware/cad/design-control/registry.json").write_text(
        json.dumps({"delivery": {"path": "kit.json", "sha256": "example"}})
    )
    result, summary = run_check(project, report())
    assert result.returncode == 0
    assert "Kit delivery selected; selection is not qualification" in summary
    assert "0 outstanding release reviews" in summary


@pytest.mark.parametrize("registry", ["{", "[]", "{}", '{"delivery": false}'])
def test_missing_or_invalid_delivery_status_fails(project, registry):
    (project / "hardware/cad/design-control/registry.json").write_text(registry)
    result, summary = run_check(project, report())
    assert result.returncode == 1
    assert "Input integrity: FAIL" in summary


def test_summary_displays_review_text_literally(project):
    result, summary = run_check(
        project, report(blockers=["</pre><script>bad</script>"])
    )
    assert result.returncode == 0
    assert "<script>" not in summary
    assert "&lt;/pre&gt;&lt;script&gt;bad&lt;/script&gt;" in summary


def test_guide_review_remains_visible(project):
    payload = report()
    payload["stages"]["guide"]["instructions"] = {
        "status": "pending",
        "reason": "Fit unconfirmed",
    }
    payload["blockers"] = ["instructions: pending — Fit unconfirmed"]
    result, summary = run_check(project, payload)
    assert result.returncode == 0
    assert "instructions: pending — Fit unconfirmed" in summary


@pytest.mark.parametrize("stage", ["cad", "render-inputs", "printing", "guide"])
def test_success_requires_every_stage(project, stage):
    payload = report()
    del payload["stages"][stage]
    result, summary = run_check(project, payload)
    assert result.returncode == 1
    assert "missing stage" in summary


def test_pending_reviews_cannot_disappear_from_summary(project):
    payload = report(blockers=["Geometry comparison pending"])
    payload["blockers"] = []
    result, summary = run_check(project, payload)
    assert result.returncode == 1
    assert "review summary disagrees" in summary


def test_omitted_guide_surface_cannot_hide_pending_review(project):
    payload = report()
    del payload["stages"]["guide"]["instructions"]
    result, summary = run_check(project, payload)
    assert result.returncode == 1
    assert "missing required review surfaces" in summary


def test_pages_requires_integrity_build_and_browser_before_upload():
    workflow = (ROOT / ".github/workflows/guide-pages.yml").read_text()
    steps = [
        "run: python scripts/check_pages.py",
        "run: make guide-setup GUIDE_SYSTEM_DEPS=1",
        "run: make guide-browser HOST_PYTHON=python",
        "uses: actions/upload-pages-artifact@",
    ]
    positions = [workflow.index(step) for step in steps]
    assert positions == sorted(positions)
    assert "continue-on-error" not in workflow
    assert "needs: build" in workflow
