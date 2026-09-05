"""Regression tests for executed-fit model lineage."""

from __future__ import annotations

import csv
import json
import runpy
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_model_lineage.py"
CONTRACT = ROOT / "governance" / "model_lineage_contract.json"
RAW_RESULTS = (
    ROOT / "results" / "adult" / "split_sensitivity.csv",
    ROOT / "results" / "adult" / "seed_sensitivity.csv",
    ROOT / "results" / "adult" / "preprocessing_sensitivity.csv",
    ROOT / "results" / "adult" / "factorial.csv",
)


def _load_contract() -> dict[str, Any]:
    payload: Any = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _build_records() -> list[dict[str, object]]:
    namespace = runpy.run_path(str(SCRIPT), run_name="model_lineage_renderer")
    builder = cast(Callable[[Path], list[dict[str, object]]], namespace["build_records"])
    return builder(ROOT)


def test_executed_fit_lineage_covers_all_committed_fits() -> None:
    records = _build_records()
    assert len(records) == 636
    assert len({record["fit_evidence_id"] for record in records}) == 636


def test_lineage_ids_are_deterministic() -> None:
    assert _build_records() == _build_records()


def test_lineage_preserves_family_fit_counts() -> None:
    counts = Counter(str(record["experiment"]) for record in _build_records())
    assert counts == {
        "split_sensitivity": 120,
        "seed_sensitivity": 120,
        "preprocessing_sensitivity": 12,
        "factorial": 384,
    }


def test_lineage_layers_are_present_for_every_fit() -> None:
    required = {
        "fit_evidence_id",
        "execution_spec_id",
        "training_spec_id",
        "partition_spec_id",
        "preprocessing_spec_id",
        "model_spec_id",
        "prediction_sha256",
        "score_sha256",
    }
    for record in _build_records():
        assert required.issubset(record)
        for field in required - {"prediction_sha256", "score_sha256"}:
            assert str(record[field]).startswith("sha256:")


def test_declared_result_evidence_fields_exist_in_every_raw_family() -> None:
    declared = set(_load_contract()["result_evidence_fields"])
    for path in RAW_RESULTS:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames is not None
            assert declared.issubset(reader.fieldnames)


def test_model_lineage_contract_keeps_production_boundaries_explicit() -> None:
    payload = _load_contract()
    assert payload["expected_fit_records"] == 636
    assert payload["scope_boundaries"] == {
        "trained_model_binary_persisted": False,
        "production_model_registry": False,
        "approval_state_lineage": False,
        "deployment_endpoint_lineage": False,
    }
