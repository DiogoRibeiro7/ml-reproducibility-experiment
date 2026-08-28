"""Release-gate regression tests."""

import shutil
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from ml_reproducibility.config import load_config
from ml_reproducibility.data import load_breast_cancer_smoke
from ml_reproducibility.design import freeze_design
from ml_reproducibility.experiment import (
    factorial_specs,
    preprocessing_sensitivity_specs,
    run_specs,
    seed_sensitivity_specs,
    split_sensitivity_specs,
)
from ml_reproducibility.provenance import write_manifest
from ml_reproducibility.release import _verify_full_empirical_replay, _verify_manifest
from ml_reproducibility.serialization import write_csv


def test_full_replay_detects_coordinated_raw_result_tampering(tmp_path: Path) -> None:
    """A syntactically valid altered non-reference row must fail independent replay."""

    root = Path(__file__).resolve().parents[1]
    base = load_config(root / "configs" / "smoke.yml")
    cfg = replace(
        base,
        models=("sgd_logistic",),
        factorial_models=("sgd_logistic",),
        split_repetitions=2,
        seed_repetitions=2,
        factorial_split_repetitions=2,
        factorial_seed_repetitions=2,
        preprocessing=("standard", "none"),
    )
    bundle = load_breast_cancer_smoke()
    frames = {
        "split_sensitivity": run_specs(bundle, cfg, split_sensitivity_specs(cfg)),
        "seed_sensitivity": run_specs(bundle, cfg, seed_sensitivity_specs(cfg)),
        "preprocessing_sensitivity": run_specs(
            bundle, cfg, preprocessing_sensitivity_specs(cfg)
        ),
        "factorial": run_specs(bundle, cfg, factorial_specs(cfg)),
    }
    target = frames["seed_sensitivity"].copy()
    target.loc[target.index[-1], "prediction_sha256"] = "1" * 64
    target.loc[target.index[-1], "score_sha256"] = "2" * 64
    target.loc[target.index[-1], "roc_auc"] = 0.5
    frames["seed_sensitivity"] = target

    with pytest.raises(ValueError, match="Full replay"):
        _verify_full_empirical_replay(root=tmp_path, cfg=cfg, frames=frames)


def test_full_replay_rejects_tampered_score_diagnostics(tmp_path: Path) -> None:
    """Score diagnostics are replayed exactly, so editing them cannot pass the gate.

    The diagnostics are what make a degenerate score vector visible. If they could be
    rewritten independently of the fit, a run whose scores collapsed could be presented as
    healthy while still matching on every other column.
    """

    root = Path(__file__).resolve().parents[1]
    base = load_config(root / "configs" / "smoke.yml")
    cfg = replace(
        base,
        models=("sgd_logistic",),
        factorial_models=("sgd_logistic",),
        split_repetitions=2,
        seed_repetitions=2,
        factorial_split_repetitions=2,
        factorial_seed_repetitions=2,
        preprocessing=("standard", "none"),
    )
    bundle = load_breast_cancer_smoke()
    frames = {
        "split_sensitivity": run_specs(bundle, cfg, split_sensitivity_specs(cfg)),
        "seed_sensitivity": run_specs(bundle, cfg, seed_sensitivity_specs(cfg)),
        "preprocessing_sensitivity": run_specs(
            bundle, cfg, preprocessing_sensitivity_specs(cfg)
        ),
        "factorial": run_specs(bundle, cfg, factorial_specs(cfg)),
    }
    target = frames["preprocessing_sensitivity"].copy()
    # Claim a healthy, well-spread score vector for the unscaled run.
    target.loc[target.index[-1], "n_unique_scores"] = 999_999
    frames["preprocessing_sensitivity"] = target

    with pytest.raises(ValueError, match="Full replay"):
        _verify_full_empirical_replay(root=tmp_path, cfg=cfg, frames=frames)


def _manifest_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create a minimal design tree with one output and its manifest."""
    source = Path(__file__).resolve().parents[1]
    for relative in (
        "configs/smoke.yml",
        "docs/PROTOCOL.md",
        "docs/STUDY_DESIGN.md",
        "pyproject.toml",
        "environment/requirements.lock.txt",
        "environment/runtime-policy.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    package = tmp_path / "src" / "ml_reproducibility"
    package.mkdir(parents=True, exist_ok=True)
    for source_file in (source / "src" / "ml_reproducibility").glob("*.py"):
        shutil.copy2(source_file, package / source_file.name)

    config = tmp_path / "configs" / "smoke.yml"
    lock = freeze_design(tmp_path, config)
    output = tmp_path / "results" / "smoke" / "split_sensitivity.csv"
    write_csv(pd.DataFrame({"roc_auc": [0.5]}), output)
    manifest = tmp_path / "results" / "smoke" / "split_sensitivity.manifest.json"
    write_manifest(
        manifest,
        experiment_name="split_sensitivity",
        root=tmp_path,
        config_path=config,
        design_lock=lock,
        dataset_provenance={"name": "test", "n_rows": 10},
        outputs=[output],
        execution_policy={"n_jobs": 1, "numeric_threads": 1},
    )
    return config, lock, output, manifest


def test_manifest_rejects_forged_dataset_provenance(tmp_path: Path) -> None:
    """A manifest may not claim results came from data other than the verified dataset.

    The self-hash only proves the manifest is internally consistent, so it can be
    recomputed after an edit. Binding the recorded provenance to the real dataset is what
    makes the claim checkable.
    """

    config, lock, output, manifest = _manifest_fixture(tmp_path)
    cfg = load_config(config)

    _verify_manifest(
        root=tmp_path,
        config_path=config,
        lock_path=lock,
        result_paths=[output],
        manifest_path=manifest,
        cfg=cfg,
        expected_dataset={"name": "test", "n_rows": 10},
    )

    with pytest.raises(ValueError, match="Dataset provenance mismatch"):
        _verify_manifest(
            root=tmp_path,
            config_path=config,
            lock_path=lock,
            result_paths=[output],
            manifest_path=manifest,
            cfg=cfg,
            expected_dataset={"name": "test", "n_rows": 999_999},
        )


def test_manifest_requires_every_bound_output(tmp_path: Path) -> None:
    """A manifest must bind exactly the outputs it is verified against."""

    config, lock, output, manifest = _manifest_fixture(tmp_path)
    cfg = load_config(config)
    extra = tmp_path / "results" / "smoke" / "seed_sensitivity.csv"
    write_csv(pd.DataFrame({"roc_auc": [0.6]}), extra)

    with pytest.raises(ValueError, match="Output hash mismatch"):
        _verify_manifest(
            root=tmp_path,
            config_path=config,
            lock_path=lock,
            result_paths=[output, extra],
            manifest_path=manifest,
            cfg=cfg,
        )
