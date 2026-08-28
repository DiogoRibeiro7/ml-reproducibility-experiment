"""Configuration validation tests."""

from pathlib import Path

from ml_reproducibility.config import load_config


def test_smoke_config_loads() -> None:
    """The repository smoke configuration must remain valid."""

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "smoke.yml")
    assert cfg.dataset == "breast_cancer"
    assert cfg.split_repetitions == 3
    assert cfg.n_jobs == 1
