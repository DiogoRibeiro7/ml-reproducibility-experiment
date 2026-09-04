"""Regression tests for the generated governance audit report."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_governance_audit.py"
REPORT = ROOT / "governance" / "audit_report.md"


def test_committed_governance_audit_is_current() -> None:
    """The committed audit report must equal a fresh render of repository evidence."""
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_governance_audit_surfaces_core_evidence_and_boundaries() -> None:
    """The generated report must expose the main audit claims and honest limits."""
    report = REPORT.read_text(encoding="utf-8")

    assert "636 committed fits across 4 families" in report
    assert "14/14 checks passed" in report
    assert "```mermaid" in report
    assert "`production_model_registry` | **No**" in report
    assert "`separate_validation_set_registry` | **No**" in report
