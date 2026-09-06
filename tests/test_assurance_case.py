"""Regression tests for the governance assurance case."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASSURANCE = ROOT / "governance" / "assurance_case.json"
CONTROLS = ROOT / "governance" / "control_catalog.json"
RISKS = ROOT / "governance" / "risk_register.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_assurance_claim_ids_are_unique_and_complete() -> None:
    payload = _load_json(ASSURANCE)
    claims = payload["claims"]
    ids = [claim["claim_id"] for claim in claims]
    assert len(ids) == len(set(ids))
    assert len(claims) == 8
    for claim in claims:
        assert claim["claim"]
        assert claim["controls"]
        assert claim["risks"]
        assert claim["evidence"]
        assert claim["qualification"]


def test_claims_reference_existing_controls_and_risks() -> None:
    assurance = _load_json(ASSURANCE)
    control_ids = {control["control_id"] for control in _load_json(CONTROLS)["controls"]}
    risk_ids = {risk["risk_id"] for risk in _load_json(RISKS)["risks"]}

    for claim in assurance["claims"]:
        assert set(claim["controls"]).issubset(control_ids)
        assert set(claim["risks"]).issubset(risk_ids)


def test_claim_evidence_paths_exist() -> None:
    assurance = _load_json(ASSURANCE)
    for claim in assurance["claims"]:
        for evidence in claim["evidence"]:
            assert (ROOT / evidence).is_file(), f"Missing assurance evidence: {evidence}"


def test_assurance_case_preserves_nonclaims() -> None:
    payload = _load_json(ASSURANCE)
    unsupported = set(payload["unsupported_claims"])
    required = {
        "enterprise RBAC or privileged-access governance",
        "privacy, consent, retention, or lawful-basis compliance",
        "production model registry and approval workflow",
        "deployment or rollback lineage",
        "formal organizational risk acceptance",
        "NIST AI RMF conformance",
        "ISO/IEC 42001 certification",
        "EU AI Act compliance",
        "independent audit or conformity-assessment opinion",
    }
    assert required.issubset(unsupported)
    semantics = payload["semantics"].lower()
    assert "not a compliance opinion" in semantics
    assert "not a compliance" in semantics or "not a certification" in semantics


def test_every_claim_has_a_qualification_boundary() -> None:
    payload = _load_json(ASSURANCE)
    for claim in payload["claims"]:
        qualification = claim["qualification"].lower()
        assert len(qualification) > 20
        assert any(token in qualification for token in ("not ", "does not", "cannot", "remain"))
