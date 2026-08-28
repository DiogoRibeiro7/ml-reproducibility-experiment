"""Release-gate regression tests."""

from dataclasses import replace
from pathlib import Path

import pytest

from ml_reproducibility.config import load_config
from ml_reproducibility.data import load_breast_cancer_smoke
from ml_reproducibility.experiment import (
    factorial_specs,
    preprocessing_sensitivity_specs,
    run_specs,
    seed_sensitivity_specs,
    split_sensitivity_specs,
)
from ml_reproducibility.release import _verify_full_empirical_replay


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
