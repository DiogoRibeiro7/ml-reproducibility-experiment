"""Execution engine for split, seed, preprocessing and crossed experiments."""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from .config import ExperimentConfig
from .data import DatasetBundle
from .metrics import score_classifier
from .models import build_model
from .preprocessing import build_preprocessor
from .serialization import write_csv


@dataclass(frozen=True)
class RunSpec:
    """One fully specified model fit."""

    model: str
    split_seed: int
    model_seed: int
    preprocessing: str
    experiment: str


def _iteration_count(estimator: object) -> int:
    """Return the maximum reported optimiser iteration count, or -1 when unavailable."""

    value = getattr(estimator, "n_iter_", None)
    if value is None:
        return -1
    array = np.asarray(value)
    if array.size == 0:
        return -1
    return int(np.max(array))


def _single_run(
    bundle: DatasetBundle,
    cfg: ExperimentConfig,
    spec: RunSpec,
) -> dict[str, object]:
    """Execute one leakage-safe train/test experiment and return a flat result row."""

    X_train, X_test, y_train, y_test = train_test_split(
        bundle.X,
        bundle.y,
        test_size=cfg.test_size,
        random_state=spec.split_seed,
        stratify=bundle.y,
    )
    pipeline = Pipeline(
        [
            ("preprocess", build_preprocessor(bundle.X, variant=spec.preprocessing)),
            (
                "model",
                build_model(spec.model, random_state=spec.model_seed, n_jobs=cfg.n_jobs),
            ),
        ]
    )

    with threadpool_limits(limits=cfg.numeric_threads):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", category=ConvergenceWarning)
            pipeline.fit(X_train, y_train)
        metrics = score_classifier(pipeline, X_test, y_test)

    convergence_warnings = [
        warning for warning in caught if issubclass(warning.category, ConvergenceWarning)
    ]
    estimator = pipeline.named_steps["model"]

    return {
        "experiment": spec.experiment,
        "model": spec.model,
        "split_seed": spec.split_seed,
        "model_seed": spec.model_seed,
        "preprocessing": spec.preprocessing,
        "n_train": int(X_train.shape[0]),
        "n_test": int(X_test.shape[0]),
        "converged": len(convergence_warnings) == 0,
        "convergence_warning_count": len(convergence_warnings),
        "n_iter": _iteration_count(estimator),
        **metrics,
    }


def run_specs(
    bundle: DatasetBundle,
    cfg: ExperimentConfig,
    specs: Iterable[RunSpec],
) -> pd.DataFrame:
    """Execute a sequence of run specifications in deterministic order."""

    rows = [_single_run(bundle, cfg, spec) for spec in specs]
    return pd.DataFrame(rows)


def split_sensitivity_specs(cfg: ExperimentConfig) -> list[RunSpec]:
    """Generate runs varying only the train/test split seed."""

    return [
        RunSpec(
            model=model,
            split_seed=split_seed,
            model_seed=cfg.baseline_model_seed,
            preprocessing=cfg.reference_preprocessing,
            experiment="split_sensitivity",
        )
        for model in cfg.models
        for split_seed in cfg.split_seed_grid()
    ]


def seed_sensitivity_specs(cfg: ExperimentConfig) -> list[RunSpec]:
    """Generate runs varying only the estimator random state."""

    return [
        RunSpec(
            model=model,
            split_seed=cfg.baseline_split_seed,
            model_seed=model_seed,
            preprocessing=cfg.reference_preprocessing,
            experiment="seed_sensitivity",
        )
        for model in cfg.models
        for model_seed in cfg.seed_grid()
    ]


def preprocessing_sensitivity_specs(cfg: ExperimentConfig) -> list[RunSpec]:
    """Generate runs varying only the declared preprocessing procedure."""

    return [
        RunSpec(
            model=model,
            split_seed=cfg.baseline_split_seed,
            model_seed=cfg.baseline_model_seed,
            preprocessing=variant,
            experiment="preprocessing_sensitivity",
        )
        for model in cfg.models
        for variant in cfg.preprocessing
    ]


def factorial_specs(cfg: ExperimentConfig) -> list[RunSpec]:
    """Generate balanced crossed designs for every declared stochastic estimator."""

    return [
        RunSpec(
            model=model,
            split_seed=cfg.baseline_split_seed + split_offset,
            model_seed=cfg.baseline_model_seed + model_offset,
            preprocessing=variant,
            experiment="factorial",
        )
        for model in cfg.factorial_models
        for split_offset in range(cfg.factorial_split_repetitions)
        for model_offset in range(cfg.factorial_seed_repetitions)
        for variant in cfg.preprocessing
    ]


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    """Save a result table in a stable row order."""

    write_csv(
        frame.sort_values(
            ["experiment", "model", "split_seed", "model_seed", "preprocessing"],
            kind="stable",
        ),
        path,
    )
