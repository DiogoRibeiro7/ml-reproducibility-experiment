"""Regression tests for the evidence-backed governance risk register."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "governance" / "risk_register.json"
CATALOG = ROOT / "governance" / "control_catalog.json"


def _load(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_risk_ids_are_unique_and_required_fields_present() -> None:
    register = _load(REGISTER)
    risks = register["risks"]
    ids = [risk["risk_id"] for risk in risks]
    assert len(ids) == len(set(ids))
    required = {
        "risk_id",
        "risk_statement",
        "category",
        "evidence",
        "mitigating_controls",
        "treatment",
        "current_mitigation",
        "residual_state",
        "residual_risk",
        "next_evidence_step",
    }
    for risk in risks:
        assert required.issubset(risk)


def test_every_risk_evidence_path_exists() -> None:
    register = _load(REGISTER)
    for risk in register["risks"]:
        assert risk["evidence"]
        for relative in risk["evidence"]:
            assert (ROOT / relative).is_file(), f"Missing evidence: {relative}"


def test_mitigating_controls_exist_in_catalog() -> None:
    register = _load(REGISTER)
    catalog = _load(CATALOG)
    control_ids = {control["control_id"] for control in catalog["controls"]}
    for risk in register["risks"]:
        assert risk["mitigating_controls"]
        assert set(risk["mitigating_controls"]).issubset(control_ids)


def test_treatments_and_residual_states_are_constrained() -> None:
    register = _load(REGISTER)
    allowed_treatments = set(register["allowed_treatments"])
    allowed_states = set(register["allowed_residual_states"])
    for risk in register["risks"]:
        assert risk["treatment"] in allowed_treatments
        assert risk["residual_state"] in allowed_states


def test_register_does_not_invent_organizational_risk_acceptance() -> None:
    boundary = _load(REGISTER)["governance_boundary"]
    assert boundary["risk_acceptance_authority_recorded"] is False
    assert boundary["organizational_risk_owner_recorded"] is False
    assert boundary["formal_enterprise_risk_rating_claimed"] is False


def test_known_open_risks_remain_explicit() -> None:
    risks = {risk["risk_id"]: risk for risk in _load(REGISTER)["risks"]}
    assert risks["RISK-01"]["residual_state"] == "open"
    assert "second" in risks["RISK-01"]["next_evidence_step"].lower()
    assert risks["RISK-05"]["treatment"] == "successor_study"
    assert risks["RISK-06"]["residual_state"] == "bounded_by_scope"
