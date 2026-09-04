"""Regression tests for the generated governance audit report."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Callable, cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_governance_audit.py"
REPORT = ROOT / "governance" / "audit_report.md"


def _build_report() -> str:
    """Render the governance report directly from the standalone script."""
    namespace = runpy.run_path(str(SCRIPT), run_name="governance_audit_renderer")
    build_report = cast(Callable[[Path], str], namespace["build_report"])
    return build_report(ROOT)


def test_committed_governance_audit_is_current() -> None:
    """The committed audit report must equal a fresh render of repository evidence."""
    assert REPORT.read_text(encoding="utf-8") == _build_report()


def test_governance_audit_surfaces_core_evidence_and_boundaries() -> None:
    """The generated report must expose the main audit claims and honest limits."""
    report = REPORT.read_text(encoding="utf-8")

    assert "636 committed fits across 4 families" in report
    assert "14/14 checks passed" in report
    assert "```mermaid" in report
    assert "`production_model_registry` | **No**" in report
    assert "`separate_validation_set_registry` | **No**" in report
