"""Statistical summaries and reproducibility diagnostics."""

from __future__ import annotations

import math
from itertools import combinations
from pathlib import Path
from typing import Any, Final

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from numpy.typing import NDArray
from statsmodels.formula.api import ols

from .config import ExperimentConfig
from .models import STOCHASTIC_MODELS

METRICS: Final[tuple[str, ...]] = ("accuracy", "balanced_accuracy", "f1", "roc_auc")
TOLERANCE_NUMERIC_SLACK: Final[float] = 1.0e-12


def wilson_interval(
    successes: int, trials: int, *, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion.

    The Wald interval is unusable here: reproduction rates are routinely at or near 0 and
    1, where it produces zero width or limits outside [0, 1].
    """

    if trials <= 0:
        return (float("nan"), float("nan"))
    phat = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (phat + z * z / (2.0 * trials)) / denominator
    half = (z / denominator) * math.sqrt(
        phat * (1.0 - phat) / trials + z * z / (4.0 * trials * trials)
    )
    return (max(0.0, centre - half), min(1.0, centre + half))


def _pairwise_rate(values: NDArray[np.float64], tolerance: float) -> float:
    """Return the fraction of unordered run pairs agreeing within *tolerance*."""

    drift = np.asarray([abs(a - b) for a, b in combinations(values, 2)], dtype=float)
    return float(np.mean(drift <= tolerance + TOLERANCE_NUMERIC_SLACK))


def jackknife_interval(
    values: NDArray[np.float64], tolerance: float, *, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Return a delete-one-run jackknife interval for the pairwise reproduction rate.

    The pairwise rate is a U-statistic over all C(n, 2) pairs of runs. Those pairs are not
    independent -- each run appears in n-1 of them -- so treating the pair count as a
    binomial sample size would badly understate the uncertainty. Resampling whole runs
    respects the dependence.
    """

    n = int(values.size)
    if n < 3:
        return (float("nan"), float("nan"))
    full = _pairwise_rate(values, tolerance)
    leave_one_out = np.asarray(
        [_pairwise_rate(np.delete(values, index), tolerance) for index in range(n)],
        dtype=float,
    )
    pseudo = n * full - (n - 1) * leave_one_out
    variance = float(np.var(pseudo, ddof=1)) / n
    if not math.isfinite(variance) or variance <= 0.0:
        return (full, full)
    half = z * math.sqrt(variance)
    return (max(0.0, full - half), min(1.0, full + half))


def summarise(frame: pd.DataFrame, *, grouping: list[str]) -> pd.DataFrame:
    """Summarise metric location and dispersion by selected factors."""

    summary = (
        frame.groupby(grouping, dropna=False)[list(METRICS)]
        .agg(["count", "mean", "std", "min", "max"])
        .reset_index()
    )
    summary.columns = [
        "_".join(str(part) for part in column if str(part))
        if isinstance(column, tuple)
        else str(column)
        for column in summary.columns
    ]
    return summary


def _reference_mask(
    group: pd.DataFrame, *, experiment: str, cfg: ExperimentConfig
) -> pd.Series[Any]:
    """Identify the one prospectively declared reference row in a result family.

    The reference is taken from the declared design rather than from the position of a
    row inside the frame. Selecting it by, say, the smallest split seed would silently
    redefine the primary estimand if the seed grid were ever centred on the baseline or
    otherwise reordered.
    """

    mask: pd.Series[Any]
    if experiment == "split_sensitivity":
        mask = (group["split_seed"] == cfg.baseline_split_seed) & (
            group["model_seed"] == cfg.baseline_model_seed
        )
    elif experiment == "seed_sensitivity":
        mask = (group["model_seed"] == cfg.baseline_model_seed) & (
            group["split_seed"] == cfg.baseline_split_seed
        )
    elif experiment == "preprocessing_sensitivity":
        mask = group["preprocessing"] == cfg.reference_preprocessing
    else:
        raise ValueError(f"Unsupported reproducibility family: {experiment}")
    if int(mask.sum()) != 1:
        raise ValueError(
            f"Expected exactly one reference row for {experiment}, found {int(mask.sum())}"
        )
    return mask


def _reference_value(
    group: pd.DataFrame, *, experiment: str, metric: str, cfg: ExperimentConfig
) -> float:
    """Return the prospectively declared reference value for one model/family."""

    mask = _reference_mask(group, experiment=experiment, cfg=cfg)
    return float(group.loc[mask, metric].iloc[0])


def reproducibility_summary(
    frame: pd.DataFrame,
    *,
    experiment: str,
    metric: str,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    """Quantify absolute drift of genuine reruns or alternatives from the reference."""

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    rows: list[dict[str, object]] = []
    for model, group in frame.groupby("model", sort=True):
        reference = _reference_value(group, experiment=experiment, metric=metric, cfg=cfg)
        mask = _reference_mask(group, experiment=experiment, cfg=cfg)
        comparison = group.loc[~mask, metric].to_numpy(dtype=float)
        if comparison.size == 0:
            raise ValueError(f"No non-reference observations for {experiment}/{model}")
        drift = np.abs(comparison - reference)
        rows.append(
            {
                "experiment": experiment,
                "model": str(model),
                "metric": metric,
                "reference": reference,
                "n_nonreference": int(comparison.size),
                "mean_nonreference": float(np.mean(comparison)),
                "std_nonreference": (
                    float(np.std(comparison, ddof=1)) if comparison.size > 1 else 0.0
                ),
                "median_abs_drift": float(np.median(drift)),
                "q95_abs_drift": float(np.quantile(drift, 0.95)),
                "max_abs_drift": float(np.max(drift)),
            }
        )
    return pd.DataFrame(rows)


def reference_reproducibility_curve(
    frame: pd.DataFrame,
    *,
    experiment: str,
    metric: str,
    tolerances: tuple[float, ...],
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    """Estimate rerun probability conditional on the prospectively fixed reference result.

    The reference row is excluded from both numerator and denominator. The estimand is
    defined only for factors generated by a repeated-run mechanism (split and model seed).
    """

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    if experiment not in {"split_sensitivity", "seed_sensitivity"}:
        raise ValueError("Reference reproduction probability is defined only for split/seed reruns")
    rows: list[dict[str, object]] = []
    for model, group in frame.groupby("model", sort=True):
        reference = _reference_value(group, experiment=experiment, metric=metric, cfg=cfg)
        mask = _reference_mask(group, experiment=experiment, cfg=cfg)
        values = group.loc[~mask, metric].to_numpy(dtype=float)
        drift = np.abs(values - reference)
        # A seed rerun of an estimator with no stochastic component reproduces by
        # construction. Flagging it keeps a tautology from reading as an estimate.
        deterministic = experiment == "seed_sensitivity" and str(model) not in STOCHASTIC_MODELS
        for tolerance in tolerances:
            hits = drift <= tolerance + TOLERANCE_NUMERIC_SLACK
            reproduced = int(np.count_nonzero(hits))
            lower, upper = wilson_interval(reproduced, int(values.size))
            rows.append(
                {
                    "experiment": experiment,
                    "model": str(model),
                    "metric": metric,
                    "tolerance": float(tolerance),
                    "reference": reference,
                    "n_replications": int(values.size),
                    "n_reproduced": reproduced,
                    "reference_reproduction_rate": float(np.mean(hits)),
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "ci_method": "wilson_95",
                    "deterministic_by_construction": bool(deterministic),
                }
            )
    return pd.DataFrame(rows)


def pairwise_reproducibility_curve(
    frame: pd.DataFrame,
    *,
    experiment: str,
    metric: str,
    tolerances: tuple[float, ...],
) -> pd.DataFrame:
    """Estimate intrinsic reproducibility between two legitimate independent runs."""

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    if experiment not in {"split_sensitivity", "seed_sensitivity"}:
        raise ValueError("Pairwise reproduction probability is defined only for split/seed reruns")
    rows: list[dict[str, object]] = []
    for model, group in frame.groupby("model", sort=True):
        values = group[metric].to_numpy(dtype=float)
        pair_drift = np.asarray([abs(a - b) for a, b in combinations(values, 2)], dtype=float)
        if pair_drift.size == 0:
            raise ValueError(
                f"At least two runs are required for pairwise reproducibility: {model}"
            )
        deterministic = experiment == "seed_sensitivity" and str(model) not in STOCHASTIC_MODELS
        for tolerance in tolerances:
            hits = pair_drift <= tolerance + TOLERANCE_NUMERIC_SLACK
            lower, upper = jackknife_interval(values, float(tolerance))
            rows.append(
                {
                    "experiment": experiment,
                    "model": str(model),
                    "metric": metric,
                    "tolerance": float(tolerance),
                    "n_runs": int(values.size),
                    "n_pairs": int(pair_drift.size),
                    "n_reproduced_pairs": int(np.count_nonzero(hits)),
                    "pairwise_reproduction_rate": float(np.mean(hits)),
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "ci_method": "jackknife_over_runs_95",
                    "deterministic_by_construction": bool(deterministic),
                }
            )
    return pd.DataFrame(rows)


def procedure_stability(
    frame: pd.DataFrame,
    *,
    metric: str,
    tolerances: tuple[float, ...],
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    """Describe finite sensitivity to the predeclared alternative preprocessing procedures."""

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    rows: list[dict[str, object]] = []
    for model, group in frame.groupby("model", sort=True):
        reference = _reference_value(
            group, experiment="preprocessing_sensitivity", metric=metric, cfg=cfg
        )
        mask = _reference_mask(group, experiment="preprocessing_sensitivity", cfg=cfg)
        alternatives = group.loc[~mask, metric].to_numpy(dtype=float)
        drift = np.abs(alternatives - reference)
        for tolerance in tolerances:
            hits = drift <= tolerance + TOLERANCE_NUMERIC_SLACK
            rows.append(
                {
                    "experiment": "preprocessing_sensitivity",
                    "model": str(model),
                    "metric": metric,
                    "tolerance": float(tolerance),
                    "reference": reference,
                    "n_alternative_procedures": int(alternatives.size),
                    "n_within_tolerance": int(np.count_nonzero(hits)),
                    "procedure_stability_fraction": float(np.mean(hits)),
                }
            )
    return pd.DataFrame(rows)


def conditional_split_seed_variability(
    split: pd.DataFrame,
    seed: pd.DataFrame,
    *,
    metric: str,
) -> pd.DataFrame:
    """Report one-factor-at-a-time split/seed variation conditional on baseline settings."""

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    rows: list[dict[str, object]] = []
    models = sorted(set(split["model"]) & set(seed["model"]))
    for model in models:
        split_values = split.loc[split["model"] == model, metric].to_numpy(dtype=float)
        seed_values = seed.loc[seed["model"] == model, metric].to_numpy(dtype=float)
        split_sd = float(np.std(split_values, ddof=1)) if len(split_values) > 1 else 0.0
        seed_sd = float(np.std(seed_values, ddof=1)) if len(seed_values) > 1 else 0.0
        ratio = split_sd / seed_sd if seed_sd > 0.0 else np.nan
        rows.append(
            {
                "model": str(model),
                "metric": metric,
                "estimand": "conditional_one_factor_at_a_time",
                "split_sd": split_sd,
                "seed_sd": seed_sd,
                "split_range": float(np.ptp(split_values)),
                "seed_range": float(np.ptp(seed_values)),
                "split_to_seed_sd_ratio": ratio,
                "seed_sd_is_zero": bool(seed_sd == 0.0),
            }
        )
    return pd.DataFrame(rows)


def behavioural_reference_match_summary(
    frame: pd.DataFrame,
    *,
    experiment: str,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    """Measure exact prediction/score matching against the fixed reference behaviour."""

    if experiment not in {"seed_sensitivity", "preprocessing_sensitivity"}:
        raise ValueError("Behavioural signatures are comparable only with a fixed test split")
    required = {"model", "prediction_sha256", "score_sha256"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Behavioural frame is missing columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    for model, group in frame.groupby("model", sort=True):
        mask = _reference_mask(group, experiment=experiment, cfg=cfg)
        reference = group.loc[mask].iloc[0]
        comparison = group.loc[~mask]
        reference_prediction = str(reference["prediction_sha256"])
        reference_score = str(reference["score_sha256"])
        prediction_match = comparison["prediction_sha256"].astype(str) == reference_prediction
        score_match = comparison["score_sha256"].astype(str) == reference_score
        rows.append(
            {
                "experiment": experiment,
                "model": str(model),
                "n_nonreference": int(len(comparison)),
                "unique_prediction_vectors_all_runs": int(group["prediction_sha256"].nunique()),
                "unique_score_vectors_all_runs": int(group["score_sha256"].nunique()),
                "exact_prediction_reference_match_rate": float(prediction_match.mean()),
                "exact_score_reference_match_rate": float(score_match.mean()),
            }
        )
    return pd.DataFrame(rows)


def factorial_anova(frame: pd.DataFrame, *, metric: str = "roc_auc") -> pd.DataFrame:
    """Compute descriptive ANOVA sensitivity shares separately for each factorial model."""

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    required = {metric, "model", "split_seed", "model_seed", "preprocessing"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Factorial frame is missing columns: {sorted(missing)}")

    formula = (
        f"{metric} ~ C(split_seed) + C(model_seed) + C(preprocessing) + "
        "C(split_seed):C(model_seed) + C(split_seed):C(preprocessing) + "
        "C(model_seed):C(preprocessing)"
    )
    tables: list[pd.DataFrame] = []
    for model, group in frame.groupby("model", sort=True):
        fitted = ols(formula, data=group).fit()
        table = (
            sm.stats.anova_lm(fitted, typ=2)
            .reset_index()
            .rename(columns={"index": "source"})
        )
        # The crossed design holds one observation per cell, so the residual line *is* the
        # unmodelled three-way interaction rather than replication error. F ratios and
        # p-values computed against it would not be valid tests of anything, so only the
        # descriptive variance decomposition is retained.
        table = table.drop(columns=[c for c in ("F", "PR(>F)") if c in table.columns])
        total_ss = float(table["sum_sq"].sum())
        table.insert(0, "model", str(model))
        table["share_total_ss"] = table["sum_sq"] / total_ss if total_ss > 0 else 0.0
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def convergence_summary(*frames: pd.DataFrame) -> pd.DataFrame:
    """Summarise optimiser convergence as an observed part of procedural reproducibility."""

    frame = pd.concat(frames, ignore_index=True)
    required = {"experiment", "model", "preprocessing", "converged", "n_iter"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Convergence frame is missing columns: {sorted(missing)}")
    grouped = frame.groupby(["experiment", "model", "preprocessing"], dropna=False)
    rows: list[dict[str, object]] = []
    for keys, group in grouped:
        experiment, model, preprocessing = keys
        converged = group["converged"].astype(bool)
        iterations = pd.to_numeric(group["n_iter"], errors="raise")
        rows.append(
            {
                "experiment": str(experiment),
                "model": str(model),
                "preprocessing": str(preprocessing),
                "n_runs": int(len(group)),
                "n_converged": int(converged.sum()),
                "convergence_rate": float(converged.mean()),
                "max_n_iter": int(iterations.max()),
                "total_convergence_warnings": int(
                    pd.to_numeric(group["convergence_warning_count"], errors="raise").sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_analysis_tables(
    *,
    split: pd.DataFrame,
    seed: pd.DataFrame,
    preprocess: pd.DataFrame,
    factorial: pd.DataFrame,
    cfg: ExperimentConfig,
) -> dict[str, pd.DataFrame]:
    """Build every derived scientific table from the four raw result families."""

    metric = cfg.primary_metric
    reference_curves = [
        reference_reproducibility_curve(
            split,
            experiment="split_sensitivity",
            metric=metric,
            tolerances=cfg.reproducibility_tolerances,
            cfg=cfg,
        ),
        reference_reproducibility_curve(
            seed,
            experiment="seed_sensitivity",
            metric=metric,
            tolerances=cfg.reproducibility_tolerances,
            cfg=cfg,
        ),
    ]
    pairwise_curves = [
        pairwise_reproducibility_curve(
            split,
            experiment="split_sensitivity",
            metric=metric,
            tolerances=cfg.reproducibility_tolerances,
        ),
        pairwise_reproducibility_curve(
            seed,
            experiment="seed_sensitivity",
            metric=metric,
            tolerances=cfg.reproducibility_tolerances,
        ),
    ]
    drifts = [
        reproducibility_summary(split, experiment="split_sensitivity", metric=metric, cfg=cfg),
        reproducibility_summary(seed, experiment="seed_sensitivity", metric=metric, cfg=cfg),
        reproducibility_summary(
            preprocess, experiment="preprocessing_sensitivity", metric=metric, cfg=cfg
        ),
    ]
    return {
        "split_summary": summarise(split, grouping=["model"]),
        "seed_summary": summarise(seed, grouping=["model"]),
        "preprocessing_summary": summarise(preprocess, grouping=["model", "preprocessing"]),
        "reproducibility_drift": pd.concat(drifts, ignore_index=True),
        "reference_reproducibility_curve": pd.concat(reference_curves, ignore_index=True),
        "pairwise_reproducibility_curve": pd.concat(pairwise_curves, ignore_index=True),
        "procedure_stability": procedure_stability(
            preprocess, metric=metric, tolerances=cfg.reproducibility_tolerances, cfg=cfg
        ),
        "conditional_split_seed_variability": conditional_split_seed_variability(
            split, seed, metric=metric
        ),
        "behavioural_reference_match": pd.concat(
            [
                behavioural_reference_match_summary(
                    seed, experiment="seed_sensitivity", cfg=cfg
                ),
                behavioural_reference_match_summary(
                    preprocess, experiment="preprocessing_sensitivity", cfg=cfg
                ),
            ],
            ignore_index=True,
        ),
        "factorial_anova_roc_auc": factorial_anova(factorial, metric=metric),
        "convergence_summary": convergence_summary(split, seed, preprocess, factorial),
    }


def plot_distributions(frame: pd.DataFrame, *, factor: str, metric: str, output: Path) -> None:
    """Plot per-model metric distributions."""

    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    models = sorted(frame["model"].unique())
    grouped = [frame.loc[frame["model"] == model, metric].to_numpy() for model in models]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(grouped, tick_labels=models)
    ax.set_title(f"{metric} sensitivity by {factor}")
    ax.set_ylabel(metric)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_anova(table: pd.DataFrame, *, output: Path) -> None:
    """Plot factorial ANOVA sensitivity shares for each stochastic estimator."""

    shown = table.loc[table["source"] != "Residual"].copy()
    pivot = shown.pivot(index="source", columns="model", values="share_total_ss").fillna(0.0)
    fig, ax = plt.subplots(figsize=(11, 5))
    pivot.plot(kind="bar", ax=ax)
    ax.set_ylabel("Share of total sum of squares")
    ax.set_title("ROC-AUC sensitivity attribution")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_reference_reproducibility_curve(
    curve: pd.DataFrame,
    *,
    experiment: str,
    output: Path,
) -> None:
    """Plot reference-conditioned reproduction probability against tolerance."""

    shown = curve.loc[curve["experiment"] == experiment].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    for model, group in shown.groupby("model", sort=True):
        ordered = group.sort_values("tolerance")
        ax.plot(
            ordered["tolerance"],
            ordered["reference_reproduction_rate"],
            marker="o",
            label=model,
        )
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Absolute ROC-AUC tolerance")
    ax.set_ylabel("Reference-conditioned reproduction rate")
    ax.set_title(experiment.replace("_", " ").title())
    ax.legend()
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)
