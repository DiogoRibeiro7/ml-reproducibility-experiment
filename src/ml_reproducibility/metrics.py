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


def score_classifier(model: Predictor, X_test: object, y_test: object) -> dict[str, object]:
    """Return performance metrics and exact prediction/score signatures."""

    y_pred = np.asarray(model.predict(X_test))
    y_true = np.asarray(y_test)

    if hasattr(model, "predict_proba"):
        proba = np.asarray(cast(object, model).predict_proba(X_test))  # type: ignore[attr-defined]
        score = proba[:, 1]
    elif hasattr(model, "decision_function"):
        score = np.asarray(
            cast(object, model).decision_function(X_test)  # type: ignore[attr-defined]
        )
    else:
        score = y_pred.astype(float)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred)),
        "roc_auc": float(roc_auc_score(y_true, score)),
        "prediction_sha256": _array_sha256(y_pred, dtype=np.dtype(np.int8)),
        "score_sha256": _array_sha256(np.asarray(score), dtype=np.dtype(np.float64)),
    }
