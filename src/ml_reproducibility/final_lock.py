"""The final experimental lock: the complete scientific specification of the study.

The design lock hashes the files that define the experiment, and the preregistration
capsule binds that hash. Both are sufficient to *detect* a change, and neither is
sufficient to *read* the specification: a reviewer holding the capsule cannot see the
forest's tree count, the seed grid, or the release criteria without also holding the exact
source tree it hashes.

This document states the experiment in full, in the open, so the commitment can be read
and checked as a scientific claim rather than only as a digest. It is generated from the
live configuration and estimator objects, never hand-written, so it cannot drift from what
the code will actually execute.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from . import __version__
from .analysis import METRICS
from .config import ExperimentConfig, load_config
from .data import ADULT_COLUMNS, ADULT_DOI, ADULT_FILES
from .design import verify_design_lock
from .experiment import (
    factorial_specs,
    preprocessing_sensitivity_specs,
    seed_sensitivity_specs,
    split_sensitivity_specs,
)
from .models import STOCHASTIC_MODELS, build_model
from .provenance import sha256_path
from .serialization import write_json

FINAL_LOCK_SCHEMA_VERSION: Final[int] = 1
MODEL_SEED_PLACEHOLDER: Final[str] = "<model_seed from the declared grid>"


def final_lock_path(root: Path, config_path: Path) -> Path:
    """Return the canonical final-experiment-lock path."""

    return root / "artifacts" / f"{config_path.stem}_final_experiment_lock.json"


def _model_specifications(cfg: ExperimentConfig) -> dict[str, object]:
    """Return every estimator's fully resolved hyperparameters.

    Read from the constructed estimator rather than transcribed, so the record cannot
    disagree with the object that will be fitted.
    """

    models: dict[str, object] = {}
    for name in cfg.models:
        estimator = build_model(name, random_state=0, n_jobs=cfg.n_jobs)
        params: dict[str, Any] = {}
        for key, value in sorted(estimator.get_params().items()):
            if isinstance(value, str | int | float | bool) or value is None:
                params[key] = value
            else:
                params[key] = repr(value)
        stochastic = name in STOCHASTIC_MODELS
        if stochastic and "random_state" in params:
            params["random_state"] = MODEL_SEED_PLACEHOLDER
        models[name] = {
            "estimator_class": f"{type(estimator).__module__}.{type(estimator).__name__}",
            "hyperparameters": params,
            "responds_to_model_seed": stochastic,
            "role": "stochastic estimator" if stochastic else "low-randomness control",
        }
    return models


def _preprocessing_specifications(cfg: ExperimentConfig) -> dict[str, object]:
    """Return the declared preprocessing procedures as an explicit description."""

    numeric_scaler = {
        "standard": "sklearn.preprocessing.StandardScaler",
        "robust": "sklearn.preprocessing.RobustScaler",
        "none": None,
    }
    return {
        variant: {
            "numeric_imputation": "median (sklearn.impute.SimpleImputer)",
            "numeric_scaler": numeric_scaler[variant],
            "categorical_imputation": "most_frequent (sklearn.impute.SimpleImputer)",
            "categorical_encoding": (
                "sklearn.preprocessing.OneHotEncoder(handle_unknown='ignore')"
            ),
            "fitted_inside_pipeline": True,
        }
        for variant in cfg.preprocessing
    }


def _grids(cfg: ExperimentConfig) -> dict[str, object]:
    """Return the exact enumerated run grid for every experiment family."""

    return {
        "split_sensitivity": {
            "models": list(cfg.models),
            "split_seeds": list(cfg.split_seed_grid()),
            "model_seed": cfg.baseline_model_seed,
            "preprocessing": cfg.reference_preprocessing,
            "n_fits": len(split_sensitivity_specs(cfg)),
        },
        "seed_sensitivity": {
            "models": list(cfg.models),
            "split_seed": cfg.baseline_split_seed,
            "model_seeds": list(cfg.seed_grid()),
            "preprocessing": cfg.reference_preprocessing,
            "n_fits": len(seed_sensitivity_specs(cfg)),
        },
        "preprocessing_sensitivity": {
            "models": list(cfg.models),
            "split_seed": cfg.baseline_split_seed,
            "model_seed": cfg.baseline_model_seed,
            "preprocessing": list(cfg.preprocessing),
            "n_fits": len(preprocessing_sensitivity_specs(cfg)),
        },
        "factorial": {
            "models": list(cfg.factorial_models),
            "split_seeds": [
                cfg.baseline_split_seed + offset
                for offset in range(cfg.factorial_split_repetitions)
            ],
            "model_seeds": [
                cfg.baseline_model_seed + offset
                for offset in range(cfg.factorial_seed_repetitions)
            ],
            "preprocessing": list(cfg.preprocessing),
            "n_fits": len(factorial_specs(cfg)),
        },
    }


def build_final_experiment_lock(root: Path, config_path: Path) -> Path:
    """Write the complete, human-readable scientific specification of the experiment."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    lock_path = verify_design_lock(root, config_path)
    design_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    runtime_policy = json.loads(
        (root / "environment" / "runtime-policy.json").read_text(encoding="utf-8")
    )
    grids = _grids(cfg)
    counts = {family: int(spec["n_fits"]) for family, spec in grids.items()}  # type: ignore[index]

    payload: dict[str, object] = {
        "final_lock_schema": FINAL_LOCK_SCHEMA_VERSION,
        "study": "ml-reproducibility-experiment",
        "software_version": __version__,
        "status": "final prospective specification; no primary results observed",
        "dataset": {
            "name": "UCI Adult" if cfg.dataset == "adult" else cfg.dataset,
            "doi": ADULT_DOI if cfg.dataset == "adult" else None,
            "source_policy": {
                filename: {"url": url, "sha256": digest}
                for filename, (url, digest) in sorted(ADULT_FILES.items())
            }
            if cfg.dataset == "adult"
            else None,
            "columns": list(ADULT_COLUMNS) if cfg.dataset == "adult" else None,
            "target": "income, mapped {<=50K: 0, >50K: 1}" if cfg.dataset == "adult" else None,
            "duplicate_policy": "retained; counts recorded as provenance",
            "combination": "adult.data and adult.test concatenated before splitting",
        },
        "train_test_procedure": {
            "method": "repeated stratified hold-out",
            "splitter": "sklearn.model_selection.train_test_split",
            "test_size": cfg.test_size,
            "stratified_on_target": True,
            "split_controlled_by": "split_seed",
        },
        "models": _model_specifications(cfg),
        "preprocessing": _preprocessing_specifications(cfg),
        "grids": grids,
        "raw_family_fit_counts": counts,
        "expected_raw_fit_count": sum(counts.values()),
        "metrics": {
            "primary": cfg.primary_metric,
            "secondary": [name for name in METRICS if name != cfg.primary_metric],
            "ranking_score_policy": (
                "decision_function when the estimator provides one, otherwise the "
                "positive-class probability; ROC-AUC is a rank statistic and the margin is "
                "the quantity the estimator ranks by"
            ),
            "csv_precision": "%.12g",
        },
        "reproducibility": {
            "tolerances": list(cfg.reproducibility_tolerances),
            "reference_specification": {
                "split_seed": cfg.baseline_split_seed,
                "model_seed": cfg.baseline_model_seed,
                "preprocessing": cfg.reference_preprocessing,
            },
            "reference_conditioned": {
                "definition": "P(|M - m0| <= eps | m0), reference excluded from numerator "
                "and denominator",
                "interval": "95% Wilson score",
            },
            "pairwise": {
                "definition": "P(|M1 - M2| <= eps) over all unordered pairs of runs",
                "interval": "95% delete-one-run jackknife; pairs are dependent",
            },
            "procedure_stability": {
                "definition": "fraction of declared alternative procedures within tolerance",
                "interval": None,
                "note": "a finite enumeration, not a sampling distribution",
            },
            "behavioural": {
                "signatures": ["prediction_sha256", "score_sha256"],
                "compared_only_when_test_set_fixed": [
                    "seed_sensitivity",
                    "preprocessing_sensitivity",
                ],
            },
        },
        "convergence_policy": {
            "recorded": ["converged", "convergence_warning_count", "n_iter"],
            "non_convergent_runs_excluded": False,
            "note": "convergence failure is an observed procedural outcome, not a defect",
        },
        "score_diagnostics": {
            "recorded": ["score_kind", "n_unique_scores", "score_abs_median"],
            "rationale": (
                "score collapse and margin explosion emit no convergence warning; recording "
                "them makes such a failure observable"
            ),
        },
        "statistical_analysis": {
            "variance_decomposition": (
                "descriptive Type II ANOVA sums of squares on the balanced crossed design, "
                "per factorial model"
            ),
            "anova_model": (
                "metric ~ C(split_seed) + C(model_seed) + C(preprocessing) + all two-way "
                "interactions; residual is the unmodelled three-way interaction"
            ),
            "f_and_p_values_reported": False,
            "derived_tables": [
                "split_summary",
                "seed_summary",
                "preprocessing_summary",
                "reproducibility_drift",
                "reference_reproducibility_curve",
                "pairwise_reproducibility_curve",
                "procedure_stability",
                "conditional_split_seed_variability",
                "behavioural_reference_match",
                "factorial_anova_roc_auc",
                "convergence_summary",
            ],
        },
        "runtime_requirements": runtime_policy,
        "release_gate_policy": {
            "checks": [
                "design_lock",
                "reference_environment",
                "external_anchor",
                "dataset",
                "raw_split_sensitivity",
                "raw_seed_sensitivity",
                "raw_preprocessing_sensitivity",
                "raw_factorial",
                "environment_consistency",
                "analysis_manifest",
                "baseline_consistency",
                "deterministic_controls",
                "derived_tables",
                "full_empirical_replay",
            ],
            "requirement": (
                "every configured raw fit is independently reconstructed; metrics must agree "
                "to the stored 12-significant-digit precision and behavioural signatures, "
                "score diagnostics and convergence outcomes must agree exactly"
            ),
            "gate_may_not_be_weakened_after_seeing_results": True,
        },
        "config_path": config_path.resolve().relative_to(root).as_posix(),
        "config_sha256": sha256_path(config_path),
        "design_lock_path": lock_path.resolve().relative_to(root).as_posix(),
        "design_lock_sha256": sha256_path(lock_path),
        "design_lock": design_lock,
    }

    destination = final_lock_path(root, config_path)
    write_json(destination, payload)
    return destination
