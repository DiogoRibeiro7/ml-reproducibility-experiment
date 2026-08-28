"""Validated configuration models for the reproducibility experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

DatasetName = Literal["adult", "breast_cancer"]
PreprocessName = Literal["standard", "robust", "none"]
ModelName = Literal["logistic", "linear_svm", "random_forest", "sgd_logistic"]

_ALLOWED_DATASETS: frozenset[str] = frozenset({"adult", "breast_cancer"})
_ALLOWED_PREPROCESSING: frozenset[str] = frozenset({"standard", "robust", "none"})
_ALLOWED_MODELS: frozenset[str] = frozenset(
    {"logistic", "linear_svm", "random_forest", "sgd_logistic"}
)


@dataclass(frozen=True)
class ExperimentConfig:
    """Fully validated prospective numerical design."""

    dataset: DatasetName
    output_dir: Path
    figure_dir: Path
    test_size: float
    baseline_split_seed: int
    baseline_model_seed: int
    split_repetitions: int
    seed_repetitions: int
    factorial_split_repetitions: int
    factorial_seed_repetitions: int
    factorial_models: tuple[ModelName, ...]
    models: tuple[ModelName, ...]
    preprocessing: tuple[PreprocessName, ...]
    reference_preprocessing: PreprocessName
    primary_metric: Literal["roc_auc"]
    reproducibility_tolerances: tuple[float, ...]
    n_jobs: int
    numeric_threads: int

    def __post_init__(self) -> None:
        """Reject incomplete or scientifically ambiguous configurations."""

        if not 0.05 <= self.test_size <= 0.5:
            raise ValueError("test_size must be between 0.05 and 0.5")
        for field_name in (
            "split_repetitions",
            "seed_repetitions",
            "factorial_split_repetitions",
            "factorial_seed_repetitions",
        ):
            value = int(getattr(self, field_name))
            if value < 2:
                raise ValueError(f"{field_name} must be >= 2")
        if self.n_jobs != 1:
            raise ValueError("n_jobs must equal 1 in the canonical reproducibility design")
        if self.numeric_threads != 1:
            raise ValueError("numeric_threads must equal 1 in the canonical reproducibility design")
        if not self.models:
            raise ValueError("At least one model must be configured")
        if not self.factorial_models:
            raise ValueError("At least one factorial model must be configured")
        unknown_factorial = set(self.factorial_models) - set(self.models)
        if unknown_factorial:
            raise ValueError(
                "Every factorial model must also appear in models: "
                f"{sorted(unknown_factorial)}"
            )
        if not self.preprocessing:
            raise ValueError("At least one preprocessing variant must be configured")
        if self.reference_preprocessing not in self.preprocessing:
            raise ValueError(
                "reference_preprocessing must appear in the declared preprocessing set"
            )
        if self.baseline_split_seed not in self.split_seed_grid():
            raise ValueError("baseline_split_seed must appear in the split-sensitivity grid")
        if self.baseline_model_seed not in self.seed_grid():
            raise ValueError("baseline_model_seed must appear in the seed-sensitivity grid")
        if not self.reproducibility_tolerances:
            raise ValueError("At least one reproducibility tolerance is required")
        if any(value <= 0.0 or value >= 1.0 for value in self.reproducibility_tolerances):
            raise ValueError("reproducibility tolerances must lie strictly between 0 and 1")
        if tuple(sorted(set(self.reproducibility_tolerances))) != self.reproducibility_tolerances:
            raise ValueError("reproducibility tolerances must be unique and increasing")


    def split_seed_grid(self) -> tuple[int, ...]:
        """Return the prospective split-sensitivity seed grid."""

        return tuple(
            self.baseline_split_seed + offset for offset in range(self.split_repetitions)
        )

    def seed_grid(self) -> tuple[int, ...]:
        """Return the prospective estimator-seed grid."""

        return tuple(
            self.baseline_model_seed + offset for offset in range(self.seed_repetitions)
        )


def _require_mapping(value: object, *, label: str) -> dict[str, Any]:
    """Return *value* as a mapping or raise a helpful type error."""

    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a mapping")
    return value


def _require_string_list(value: object, *, label: str) -> list[str]:
    """Validate a YAML list whose values are expected to be strings."""

    if not isinstance(value, list):
        raise TypeError(f"{label} must be a list")
    return [str(item) for item in value]


def load_config(path: Path) -> ExperimentConfig:
    """Load and validate an experiment YAML file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = _require_mapping(raw, label="Configuration")

    dataset = str(cfg.get("dataset", "adult"))
    if dataset not in _ALLOWED_DATASETS:
        raise ValueError(f"Unsupported dataset: {dataset}")

    preprocessing_values = _require_string_list(
        cfg.get("preprocessing", ["standard"]), label="preprocessing"
    )
    unknown_preprocessing = set(preprocessing_values) - _ALLOWED_PREPROCESSING
    if unknown_preprocessing:
        raise ValueError(f"Unsupported preprocessing: {sorted(unknown_preprocessing)}")

    model_values = _require_string_list(
        cfg.get("models", ["logistic", "linear_svm", "random_forest", "sgd_logistic"]),
        label="models",
    )
    unknown_models = set(model_values) - _ALLOWED_MODELS
    if unknown_models:
        raise ValueError(f"Unsupported models: {sorted(unknown_models)}")

    factorial_values = _require_string_list(
        cfg.get("factorial_models", ["sgd_logistic", "random_forest"]),
        label="factorial_models",
    )
    unknown_factorial = set(factorial_values) - _ALLOWED_MODELS
    if unknown_factorial:
        raise ValueError(f"Unsupported factorial models: {sorted(unknown_factorial)}")

    tolerances_raw = cfg.get("reproducibility_tolerances", [0.001, 0.005, 0.01])
    if not isinstance(tolerances_raw, list):
        raise TypeError("reproducibility_tolerances must be a list")
    tolerances = tuple(float(item) for item in tolerances_raw)

    reference_preprocessing = str(cfg.get("reference_preprocessing", "standard"))
    if reference_preprocessing not in _ALLOWED_PREPROCESSING:
        raise ValueError(f"Unsupported reference preprocessing: {reference_preprocessing}")

    primary_metric = str(cfg.get("primary_metric", "roc_auc"))
    if primary_metric != "roc_auc":
        raise ValueError("roc_auc is the only supported prospective primary metric")

    return ExperimentConfig(
        dataset=cast(DatasetName, dataset),
        output_dir=Path(str(cfg.get("output_dir", f"results/{dataset}"))),
        figure_dir=Path(str(cfg.get("figure_dir", f"figures/{dataset}"))),
        test_size=float(cfg.get("test_size", 0.25)),
        baseline_split_seed=int(cfg.get("baseline_split_seed", 1729)),
        baseline_model_seed=int(cfg.get("baseline_model_seed", 2718)),
        split_repetitions=int(cfg.get("split_repetitions", 30)),
        seed_repetitions=int(cfg.get("seed_repetitions", 30)),
        factorial_split_repetitions=int(cfg.get("factorial_split_repetitions", 8)),
        factorial_seed_repetitions=int(cfg.get("factorial_seed_repetitions", 8)),
        factorial_models=cast(tuple[ModelName, ...], tuple(factorial_values)),
        models=cast(tuple[ModelName, ...], tuple(model_values)),
        preprocessing=cast(tuple[PreprocessName, ...], tuple(preprocessing_values)),
        reference_preprocessing=cast(PreprocessName, reference_preprocessing),
        primary_metric=cast(Literal["roc_auc"], primary_metric),
        reproducibility_tolerances=tolerances,
        n_jobs=int(cfg.get("n_jobs", 1)),
        numeric_threads=int(cfg.get("numeric_threads", 1)),
    )
