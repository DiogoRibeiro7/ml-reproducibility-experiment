"""Regression tests for the non-frozen train/test partition governance layer."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "partition_contract.json"
FINAL_LOCK = ROOT / "artifacts" / "adult_final_experiment_lock.json"
RAW_RESULTS = (
    ROOT / "results" / "adult" / "split_sensitivity.csv",
    ROOT / "results" / "adult" / "seed_sensitivity.csv",
    ROOT / "results" / "adult" / "preprocessing_sensitivity.csv",
    ROOT / "results" / "adult" / "factorial.csv",
)


def _load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _seed_spec(seed: int, contract: dict[str, Any]) -> dict[str, object]:
    """Build the canonical partition-specification payload for one split seed."""
    dataset = contract["dataset_identity"]
    procedure = contract["split_procedure"]
    return {
        "dataset_source_sha256": dataset["source_files"],
        "design_lock_sha256": contract["design_lock_sha256"],
        "splitter": procedure["splitter"],
        "test_size": procedure["test_size"],
        "stratified_on_target": procedure["stratified_on_target"],
        "split_seed": seed,
        "n_rows": dataset["n_rows"],
        "n_train": procedure["n_train"],
        "n_test": procedure["n_test"],
    }


def _spec_id(seed: int, contract: dict[str, Any]) -> str:
    """Return the stable SHA-256 identity of one partition specification."""
    payload = json.dumps(
        _seed_spec(seed, contract),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _observed_rows() -> list[dict[str, str]]:
    """Load all committed primary fit rows."""
    rows: list[dict[str, str]] = []
    for path in RAW_RESULTS:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def test_partition_contract_matches_frozen_dataset_and_split_procedure() -> None:
    """The governance contract must describe the exact frozen dataset and split rule."""
    contract = _load_json(CONTRACT)
    final_lock = _load_json(FINAL_LOCK)

    assert contract["dataset_identity"]["doi"] == final_lock["dataset"]["doi"]
    expected_sources = {
        name: source["sha256"]
        for name, source in final_lock["dataset"]["source_policy"].items()
    }
    assert contract["dataset_identity"]["source_files"] == expected_sources
    assert contract["design_lock_sha256"] == final_lock["design_lock_sha256"]

    frozen = final_lock["train_test_procedure"]
    governed = contract["split_procedure"]
    assert governed["method"] == frozen["method"]
    assert governed["splitter"] == frozen["splitter"]
    assert governed["test_size"] == frozen["test_size"]
    assert governed["stratified_on_target"] == frozen["stratified_on_target"]
    assert governed["split_controlled_by"] == frozen["split_controlled_by"]


def test_committed_fits_match_governed_partition_usage() -> None:
    """Every committed fit must use a governed split seed and declared partition size."""
    contract = _load_json(CONTRACT)
    rows = _observed_rows()
    procedure = contract["split_procedure"]

    assert len(rows) == contract["total_referenced_fits"] == 636
    observed_seeds = {int(row["split_seed"]) for row in rows}
    declared = contract["declared_split_seeds"]
    expected_seeds = set(range(declared["minimum"], declared["maximum"] + 1))
    assert len(expected_seeds) == declared["count"]
    assert observed_seeds == expected_seeds

    assert {int(row["n_train"]) for row in rows} == {procedure["n_train"]}
    assert {int(row["n_test"]) for row in rows} == {procedure["n_test"]}

    observed_experiments = Counter(row["experiment"] for row in rows)
    for experiment, usage in contract["usage_by_experiment"].items():
        assert observed_experiments[experiment] == usage["fits"]


def test_partition_seed_usage_matches_each_experimental_family() -> None:
    """Split seeds observed in each family must match the frozen declared grids."""
    contract = _load_json(CONTRACT)
    rows = _observed_rows()

    seeds_by_experiment: dict[str, set[int]] = {}
    for row in rows:
        seeds_by_experiment.setdefault(row["experiment"], set()).add(int(row["split_seed"]))

    for experiment, usage in contract["usage_by_experiment"].items():
        declared = usage["split_seeds"]
        if isinstance(declared, list):
            expected = set(declared)
        else:
            expected = set(range(declared["minimum"], declared["maximum"] + 1))
            assert len(expected) == declared["count"]
        assert seeds_by_experiment[experiment] == expected


def test_baseline_partition_spec_id_is_reconstructible() -> None:
    """The baseline train/test specification must have a stable cryptographic identity."""
    contract = _load_json(CONTRACT)
    identity = contract["partition_spec_id"]
    seed = identity["baseline_split_seed"]
    assert _spec_id(seed, contract) == identity["baseline_partition_spec_id"]


def test_partition_contract_does_not_overclaim_membership_or_validation() -> None:
    """The registry must not claim evidence that is absent from the completed study."""
    contract = _load_json(CONTRACT)
    assert contract["validation_partition"]["present"] is False
    assert contract["membership_hashes"]["present"] is False
    assert "not a row-membership digest" in contract["semantics"]
