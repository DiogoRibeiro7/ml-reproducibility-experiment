"""Regression tests for the non-frozen governance lineage overlay."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "governance" / "lineage_contract.json"


def _load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object and assert that the top-level value is a mapping."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lineage_contract_matches_frozen_dataset_and_design_identity() -> None:
    """The governance overlay must point to the exact frozen Adult identities."""
    contract = _load_json(CONTRACT_PATH)
    final_lock = _load_json(ROOT / "artifacts" / "adult_final_experiment_lock.json")

    dataset_identity = contract["dataset_identity"]
    design_identity = contract["design_identity"]

    assert isinstance(dataset_identity, dict)
    assert isinstance(design_identity, dict)
    assert dataset_identity["doi"] == final_lock["dataset"]["doi"]

    source_files = dataset_identity["source_files"]
    source_policy = final_lock["dataset"]["source_policy"]
    assert isinstance(source_files, dict)
    assert isinstance(source_policy, dict)

    for file_name, expected_digest in source_files.items():
        assert expected_digest == source_policy[file_name]["sha256"]

    design_lock_path = ROOT / str(design_identity["design_lock_path"])
    capsule_path = ROOT / str(design_identity["preregistration_capsule_path"])
    assert _sha256(design_lock_path) == design_identity["design_lock_sha256"]
    assert _sha256(capsule_path) == design_identity["preregistration_capsule_sha256"]


def test_every_raw_family_manifest_binds_the_same_dataset_and_design() -> None:
    """All primary result families must share one dataset and frozen design identity."""
    contract = _load_json(CONTRACT_PATH)
    expected_design = contract["design_identity"]["design_lock_sha256"]
    expected_sources = contract["dataset_identity"]["source_files"]

    for family in contract["raw_result_families"]:
        manifest = _load_json(ROOT / family["manifest"])
        assert manifest["design_lock_sha256"] == expected_design
        assert manifest["dataset"]["raw_sha256"] == expected_sources
        assert manifest["outputs_sha256"][family["result"]] == _sha256(
            ROOT / family["result"]
        )


def test_raw_result_rows_expose_declared_per_fit_lineage() -> None:
    """Every raw result family must expose the declared reconstruction metadata."""
    contract = _load_json(CONTRACT_PATH)
    required_fields = set(contract["per_fit_lineage_fields"])

    total_rows = 0
    for family in contract["raw_result_families"]:
        result_path = ROOT / family["result"]
        with result_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames is not None
            assert required_fields.issubset(reader.fieldnames)
            rows = list(reader)

        assert len(rows) == family["expected_fits"]
        total_rows += len(rows)

    assert total_rows == 636


def test_scope_boundaries_do_not_overclaim_enterprise_governance() -> None:
    """The governance overlay must keep unsupported production claims explicitly false."""
    contract = _load_json(CONTRACT_PATH)
    boundaries = contract["scope_boundaries"]

    assert boundaries == {
        "production_model_registry": False,
        "separate_validation_set_registry": False,
        "rbac": False,
        "pii_retention_enforcement": False,
        "deployment_lineage": False,
    }
