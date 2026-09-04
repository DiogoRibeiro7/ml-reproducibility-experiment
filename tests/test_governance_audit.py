"""Regression tests for the generated governance audit report."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_governance_audit.py"
REPORT = ROOT / "governance" / "audit_report.md"


def _load_renderer() -> ModuleType:
    """Load the standalone renderer module from its repository path."""
    spec = importlib.util.spec_from_file_location("render_governance_audit", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load renderer module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_governance_audit_is_current() -> None:
    """The committed audit report must equal a fresh render of repository evidence."""
    renderer = _load_renderer()
    build_report = getattr(renderer, "build_report")
    generated = build_report(ROOT)

    assert REPORT.read_text(encoding="utf-8") == generated


def test_governance_audit_surfaces_core_evidence_and_boundaries() -> None:
    """The generated report must expose the main audit claims and honest limits."""
    report = REPORT.read_text(encoding="utf-8")

    assert "636 committed fits across 4 families" in report
    assert "14/14 checks passed" in report
    assert "```mermaid" in report
    assert "`production_model_registry` | **No**" in report
    assert "`separate_validation_set_registry` | **No**" in report
