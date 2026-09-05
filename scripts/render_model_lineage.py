"""Render deterministic lineage records for every committed Adult model fit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_FAMILIES = (
    "split_sensitivity",
    "seed_sensitivity",
    "preprocessing_sensitivity",
    "factorial",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return payload


def _canonical_id(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _partition_payload(seed: int, contract: dict[str, Any]) -> dict[str, object]:
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


def _effective_model_spec(
    model: str, model_seed: int, final_lock: dict[str, Any]
) -> dict[str, object]:
    frozen = final_lock["models"][model]
    hyperparameters = dict(frozen["hyperparameters"])
    if frozen["responds_to_model_seed"]:
        hyperparameters["random_state"] = model_seed
    return {
        "model": model,
        "estimator_class": frozen["estimator_class"],
        "hyperparameters": hyperparameters,
    }


def _family_rows(root: Path, family: str) -> list[dict[str, str]]:
    path = root / "results" / "adult" / f"{family}.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_records(root: Path) -> list[dict[str, object]]:
    """Build one lineage record for each committed primary fit."""
    final_lock = _load_json(root / "artifacts" / "adult_final_experiment_lock.json")
    partition_contract = _load_json(root / "governance" / "partition_contract.json")

    records: list[dict[str, object]] = []
    for family in RAW_FAMILIES:
        manifest_path = root / "results" / "adult" / f"{family}.manifest.json"
        manifest = _load_json(manifest_path)
        family_manifest_id = _canonical_id(manifest)

        for row in _family_rows(root, family):
            split_seed = int(row["split_seed"])
            model_seed = int(row["model_seed"])
            preprocessing = row["preprocessing"]
            model = row["model"]

            partition_spec_id = _canonical_id(
                _partition_payload(split_seed, partition_contract)
            )
            preprocessing_spec = final_lock["preprocessing"][preprocessing]
            preprocessing_spec_id = _canonical_id(
                {"name": preprocessing, "specification": preprocessing_spec}
            )
            model_spec = _effective_model_spec(model, model_seed, final_lock)
            model_spec_id = _canonical_id(model_spec)

            training_payload = {
                "dataset_source_sha256": partition_contract["dataset_identity"]["source_files"],
                "design_lock_sha256": final_lock["design_lock_sha256"],
                "partition_spec_id": partition_spec_id,
                "preprocessing_spec_id": preprocessing_spec_id,
                "model_spec_id": model_spec_id,
                "model_seed": model_seed,
            }
            training_spec_id = _canonical_id(training_payload)

            execution_payload = {
                "training_spec_id": training_spec_id,
                "experiment": family,
                "config_sha256": manifest["config_sha256"],
                "environment_sha256": manifest["environment_sha256"],
                "execution_policy": manifest["execution_policy"],
            }
            execution_spec_id = _canonical_id(execution_payload)
            fit_evidence_id = _canonical_id(
                {
                    "execution_spec_id": execution_spec_id,
                    "family_manifest_id": family_manifest_id,
                    "result_row": row,
                }
            )

            records.append(
                {
                    "fit_evidence_id": fit_evidence_id,
                    "execution_spec_id": execution_spec_id,
                    "training_spec_id": training_spec_id,
                    "partition_spec_id": partition_spec_id,
                    "preprocessing_spec_id": preprocessing_spec_id,
                    "model_spec_id": model_spec_id,
                    "experiment": family,
                    "model": model,
                    "split_seed": split_seed,
                    "model_seed": model_seed,
                    "preprocessing": preprocessing,
                    "prediction_sha256": row["prediction_sha256"],
                    "score_sha256": row["score_sha256"],
                }
            )

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("governance/model_lineage.jsonl"),
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    records = build_records(ROOT)
    text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    output.write_text(text, encoding="utf-8")
    print(f"Wrote {len(records)} lineage records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
