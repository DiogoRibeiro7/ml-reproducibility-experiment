"""Regression tests for the reproducibility estimands and score diagnostics."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from ml_reproducibility.analysis import (
    jackknife_interval,
    pairwise_reproducibility_curve,
    reference_reproducibility_curve,
    wilson_interval,
)
from ml_reproducibility.config import ExperimentConfig, load_config
from ml_reproducibility.metrics import ranking_score, score_classifier

_BASE = load_config(Path(__file__).resolve().parents[1] / "configs" / "smoke.yml")


def _cfg(**overrides: object) -> ExperimentConfig:
    """Return a smoke configuration with declared design fields overridden."""

    return replace(_BASE, **overrides)  # type: ignore[arg-type]


def _split_frame(seeds: list[int], values: list[float]) -> pd.DataFrame:
    """Build a split-sensitivity frame for one model."""

    return pd.DataFrame(
        {
            "model": ["logistic"] * len(seeds),
            "split_seed": seeds,
            "model_seed": [20] * len(seeds),
            "preprocessing": ["standard"] * len(seeds),
            "roc_auc": values,
        }
    )


def test_reference_is_the_declared_baseline_not_the_smallest_seed() -> None:
    """The reference must follow the declared design even when it is not the first row.

    Selecting the reference by ``min(split_seed)`` happens to be correct only while the
    grid starts at the baseline. A grid centred on the baseline would silently redefine
    the primary estimand, so the reference is taken from the configuration instead.
    """

    # Baseline 20 sits in the middle of the grid; the smallest seed is 18.
    frame = _split_frame([18, 19, 20, 21], [0.500, 0.600, 0.900, 0.902])
    cfg = _cfg(baseline_split_seed=20, baseline_model_seed=20, split_repetitions=4)

    curve = reference_reproducibility_curve(
        frame,
        experiment="split_sensitivity",
        metric="roc_auc",
        tolerances=(0.005,),
        cfg=cfg,
    )
    row = curve.iloc[0]
    assert row["reference"] == 0.900
    assert row["n_replications"] == 3
    # Only seed 21 (0.902) lies within 0.005 of the declared reference.
    assert row["n_reproduced"] == 1


def test_reference_curve_reports_a_wilson_interval_containing_the_estimate() -> None:
    """A reproduction rate without an interval overstates what 3 reruns can support."""

    frame = _split_frame([10, 11, 12, 13], [0.900, 0.9001, 0.9002, 0.9003])
    curve = reference_reproducibility_curve(
        frame,
        experiment="split_sensitivity",
        metric="roc_auc",
        tolerances=(0.005,),
        cfg=_cfg(baseline_split_seed=10, baseline_model_seed=20, split_repetitions=4),
    )
    row = curve.iloc[0]
    assert row["reference_reproduction_rate"] == 1.0
    assert row["ci_method"] == "wilson_95"
    # Three reruns cannot establish a rate of exactly 1; the interval must admit less.
    assert row["ci_lower"] < 1.0
    assert row["ci_upper"] == 1.0


def test_wilson_interval_stays_inside_the_unit_interval_at_the_boundary() -> None:
    """The Wald interval collapses to zero width at 0 and 1; Wilson must not."""

    lower, upper = wilson_interval(0, 29)
    assert lower == 0.0
    assert 0.0 < upper < 1.0
    lower, upper = wilson_interval(29, 29)
    assert 0.0 < lower < 1.0
    assert upper == 1.0


def test_pairwise_interval_is_wider_than_treating_pairs_as_independent() -> None:
    """Pairs share runs, so a binomial interval over C(n,2) understates uncertainty."""

    rng = np.random.default_rng(0)
    values = rng.normal(0.9, 0.004, 12)
    tolerance = 0.005

    drift = np.asarray([abs(a - b) for a, b in combinations(values, 2)], dtype=float)
    hits = int(np.count_nonzero(drift <= tolerance))
    naive_lower, naive_upper = wilson_interval(hits, int(drift.size))
    jack_lower, jack_upper = jackknife_interval(values, tolerance)

    assert (jack_upper - jack_lower) > (naive_upper - naive_lower)


def test_seed_reruns_of_deterministic_estimators_are_flagged() -> None:
    """A logistic seed rerun reproduces by construction and must not read as an estimate."""

    frame = pd.DataFrame(
        {
            "model": ["logistic"] * 3,
            "split_seed": [10] * 3,
            "model_seed": [20, 21, 22],
            "preprocessing": ["standard"] * 3,
            "roc_auc": [0.9, 0.9, 0.9],
        }
    )
    cfg = _cfg(baseline_split_seed=10, baseline_model_seed=20, seed_repetitions=3)
    curve = reference_reproducibility_curve(
        frame, experiment="seed_sensitivity", metric="roc_auc", tolerances=(0.001,), cfg=cfg
    )
    assert bool(curve.loc[0, "deterministic_by_construction"]) is True

    pairwise = pairwise_reproducibility_curve(
        frame, experiment="seed_sensitivity", metric="roc_auc", tolerances=(0.001,)
    )
    assert bool(pairwise.loc[0, "deterministic_by_construction"]) is True


class _MarginModel:
    """Estimator exposing both a margin and a saturating probability."""

    def predict(self, X: object) -> np.ndarray:
        """Return hard class labels."""

        return np.array([0, 0, 1, 1])

    def decision_function(self, X: object) -> np.ndarray:
        """Return well-separated margins that preserve the ranking."""

        return np.array([-4.0e7, -1.0e7, 2.0e7, 9.0e7])

    def predict_proba(self, X: object) -> np.ndarray:
        """Return probabilities saturated by the logistic link."""

        positive = np.array([0.0, 0.0, 1.0, 1.0])
        return np.column_stack([1.0 - positive, positive])


class _ProbaOnlyModel:
    """Estimator exposing only probabilities, as a forest does."""

    def predict(self, X: object) -> np.ndarray:
        """Return hard class labels."""

        return np.array([0, 0, 1, 1])

    def predict_proba(self, X: object) -> np.ndarray:
        """Return distinct positive-class probabilities."""

        positive = np.array([0.10, 0.30, 0.70, 0.95])
        return np.column_stack([1.0 - positive, positive])


def test_ranking_score_prefers_the_margin_over_a_saturated_probability() -> None:
    """ROC-AUC is a rank statistic, so the margin is the correct ranking input.

    An estimator fitted on unscaled features can push every probability onto {0, 1} while
    the margin still separates the observations. Ranking on the probability would discard
    that information and report a tie-dominated metric.
    """

    score, kind = ranking_score(_MarginModel(), None)
    assert kind == "decision_function"
    assert len(np.unique(score)) == 4

    proba_score, proba_kind = ranking_score(_ProbaOnlyModel(), None)
    assert proba_kind == "predict_proba"
    assert len(np.unique(proba_score)) == 4


def test_score_diagnostics_expose_a_degenerate_score_vector() -> None:
    """Score collapse produces no convergence warning, so it is recorded directly."""

    y_true = np.array([0, 0, 1, 1])
    result = score_classifier(_MarginModel(), None, y_true)
    assert result["score_kind"] == "decision_function"
    assert result["n_unique_scores"] == 4
    # A margin of this magnitude is itself the signal that the fit is pathological.
    assert float(result["score_abs_median"]) > 1.0e6

    forest = score_classifier(_ProbaOnlyModel(), None, y_true)
    assert forest["score_kind"] == "predict_proba"
    assert forest["n_unique_scores"] == 4
    assert float(forest["score_abs_median"]) < 1.0
