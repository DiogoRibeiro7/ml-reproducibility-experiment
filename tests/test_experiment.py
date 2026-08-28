"""End-to-end model-run tests on the bundled smoke dataset."""

from pathlib import Path

from ml_reproducibility.config import load_config
from ml_reproducibility.data import load_breast_cancer_smoke
from ml_reproducibility.experiment import RunSpec, factorial_specs, run_specs


def test_logistic_run_produces_valid_metrics_and_diagnostics() -> None:
    """A deterministic control should produce metrics plus convergence diagnostics."""

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "smoke.yml")
    frame = run_specs(
        load_breast_cancer_smoke(),
        cfg,
        [
            RunSpec(
                model="logistic",
                split_seed=cfg.baseline_split_seed,
                model_seed=cfg.baseline_model_seed,
                preprocessing="standard",
                experiment="test",
            )
        ],
    )
    assert len(frame) == 1
    for metric in ("accuracy", "balanced_accuracy", "f1", "roc_auc"):
        assert 0.0 <= float(frame.loc[0, metric]) <= 1.0
    assert bool(frame.loc[0, "converged"])
    assert int(frame.loc[0, "convergence_warning_count"]) == 0
    assert int(frame.loc[0, "n_iter"]) >= 0


def test_fixed_random_forest_run_is_repeatable_in_reference_environment() -> None:
    """Identical split and model seeds must recover identical reported behaviour locally."""

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "smoke.yml")
    spec = RunSpec(
        model="random_forest",
        split_seed=cfg.baseline_split_seed,
        model_seed=cfg.baseline_model_seed,
        preprocessing="standard",
        experiment="repeatability_control",
    )
    bundle = load_breast_cancer_smoke()
    first = run_specs(bundle, cfg, [spec])
    second = run_specs(bundle, cfg, [spec])
    for column in (
        "accuracy",
        "balanced_accuracy",
        "f1",
        "roc_auc",
        "prediction_sha256",
        "score_sha256",
    ):
        assert first.loc[0, column] == second.loc[0, column]


def test_factorial_grid_uses_all_declared_models() -> None:
    """The factorial generator must cross every configured factorial estimator."""

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "adult.yml")
    specs = factorial_specs(cfg)
    expected = (
        len(cfg.factorial_models)
        * cfg.factorial_split_repetitions
        * cfg.factorial_seed_repetitions
        * len(cfg.preprocessing)
    )
    assert len(specs) == expected
    assert {spec.model for spec in specs} == set(cfg.factorial_models)
