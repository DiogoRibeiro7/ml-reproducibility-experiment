"""Metric and prediction-signature calculation for binary classifiers."""

from __future__ import annotations

import hashlib
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score


class Predictor(Protocol):
    """Minimal prediction protocol needed by the experiment."""

    def predict(self, X: object) -> NDArray[np.generic]: ...


def _array_sha256(values: NDArray[np.generic], *, dtype: np.dtype[np.generic]) -> str:
    """Hash a numerical vector after canonicalising dtype and memory layout."""

    canonical = np.ascontiguousarray(values, dtype=dtype)
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def ranking_score(model: Predictor, X_test: object) -> tuple[NDArray[np.float64], str]:
    """Return the model's rank-defining score for the positive class, and its kind.

    ROC-AUC is a rank statistic, so the correct input is whatever quantity the estimator
    ranks by. ``decision_function`` is preferred because it is that quantity directly.
    ``predict_proba`` applies a saturating link on top of it, and for an estimator fitted
    on unscaled features the resulting probabilities can collapse onto {0, 1}: the ranking
    information survives in the margin but is destroyed in the probability. Preferring the
    margin keeps the metric measuring the model rather than the arithmetic of its link.

    For estimators exposing only ``predict_proba`` (such as a random forest) the positive
    class probability is itself the ranking score and is used unchanged.
    """

    if hasattr(model, "decision_function"):
        raw = cast(object, model).decision_function(X_test)  # type: ignore[attr-defined]
        return np.asarray(raw, dtype=np.float64), "decision_function"
    if hasattr(model, "predict_proba"):
        proba = np.asarray(
            cast(object, model).predict_proba(X_test),  # type: ignore[attr-defined]
            dtype=np.float64,
        )
        return proba[:, 1], "predict_proba"
    return np.asarray(model.predict(X_test), dtype=np.float64), "prediction"


def score_classifier(model: Predictor, X_test: object, y_test: object) -> dict[str, object]:
    """Return performance metrics, score diagnostics and exact behavioural signatures."""

    y_pred = np.asarray(model.predict(X_test))
    y_true = np.asarray(y_test)
    score, score_kind = ranking_score(model, X_test)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred)),
        "roc_auc": float(roc_auc_score(y_true, score)),
        # Score diagnostics. A fit whose scores collapse to very few distinct values, or
        # whose magnitude explodes, has failed in a way no convergence warning reports.
        # Recording them makes that failure an observation rather than a silent artifact.
        "score_kind": score_kind,
        "n_unique_scores": int(np.unique(score).size),
        "score_abs_median": float(np.median(np.abs(score))),
        "prediction_sha256": _array_sha256(y_pred, dtype=np.dtype(np.int8)),
        "score_sha256": _array_sha256(score, dtype=np.dtype(np.float64)),
    }
