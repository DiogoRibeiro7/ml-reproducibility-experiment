"""Regression tests for the evidence-backed governance control catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "governance" / "control_catalog.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_control_ids_are_unique_and_evidence_exists() -> None:
    catalog = _load_json(CATALOG)
    controls = catalog["controls"]
    ids = [control["control_id"] for control in controls]
    assert len(ids) == len(set(ids))
    for control in controls:
        assert control["status"] == "implemented"
        assert control["evidence"]
        for relative_path in control["evidence"]:
            assert (ROOT / relative_path).exists(), (
                f"Missing evidence for {control['control_id']}: {relative_path}"
            )


def test_framework_references_use_only_declared_frameworks() -> None:
    catalog = _load_json(CATALOG)
    declared = set(catalog["frameworks"])
    for control in catalog["controls"]:
        refs = set(control["framework_references"])
        assert refs == declared
        for values in control["framework_references"].values():
            assert values


def test_catalog_explicitly_disclaims_compliance_and_certification() -> None:
    catalog = _load_json(CATALOG)
    semantics = catalog["semantics"].lower()
    assert "not compliance" in semantics
    assert "certification" in semantics
    eu_note = catalog["frameworks"]["eu_ai_act_2024_1689"]["status_note"].lower()
    iso_note = catalog["frameworks"]["iso_iec_42001_2023"]["status_note"].lower()
    assert "does not claim" in eu_note
    assert "no clause-level conformity or certification claim" in iso_note


def test_scope_control_preserves_known_nonclaims() -> None:
    catalog = _load_json(CATALOG)
    scope = next(control for control in catalog["controls"] if control["control_id"] == "SCOPE-01")
    text = " ".join([scope["mechanism"], scope["limitations"]]).lower()
    for term in (
        "production registry",
        "rbac",
        "deployment-lineage",
        "certification",
    ):
        assert term in text
