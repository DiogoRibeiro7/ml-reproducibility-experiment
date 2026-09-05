"""Regression tests for the generated governance audit report."""

from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_governance_audit.py"
REPORT = ROOT / "governance" / "audit_report.md"


def _load_renderer() -> dict[str, object]:
    """Load the standalone renderer without executing its CLI entry point."""
    return runpy.run_path(str(SCRIPT), run_name="governance_audit_renderer")


def _build_report() -> str:
    """Render the governance report directly from repository evidence."""
    namespace = _load_renderer()
    build_report = cast(Callable[[Path], str], namespace["build_report"])
    return build_report(ROOT)


def test_committed_governance_audit_is_current() -> None:
    """The committed audit report must equal a fresh render of repository evidence."""
    assert REPORT.read_text(encoding="utf-8") == _build_report()


def test_governance_audit_surfaces_core_evidence_and_boundaries() -> None:
    """The generated report must expose the main audit claims and honest limits."""
    report = REPORT.read_text(encoding="utf-8")

    assert "636 committed fits across 4 families" in report
    assert "2 source SHA-256 values" in report
    assert "14/14 checks passed" in report
    assert "Raw result families\\n636 fits + behavioural hashes" in report
    assert "```mermaid" in report
    assert "`production_model_registry` | **No**" in report
    assert "`separate_validation_set_registry` | **No**" in report


def test_cli_writes_to_absolute_path_outside_repository(tmp_path: Path) -> None:
    """An absolute output path outside the repository must remain a supported CLI target."""
    namespace = _load_renderer()
    main = cast(Callable[[list[str] | None], int], namespace["main"])
    output = tmp_path / "governance-audit.md"

    assert main(["--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == _build_report()
