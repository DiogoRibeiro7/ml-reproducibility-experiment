"""Model registry for the classical-ML experiment."""

from __future__ import annotations

from typing import Final

from sklearn.base import ClassifierMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.svm import LinearSVC

SUPPORTED_MODELS: Final[set[str]] = {
    "logistic",
    "linear_svm",
    "random_forest",
    "sgd_logistic",
}
STOCHASTIC_MODELS: Final[set[str]] = {"random_forest", "sgd_logistic"}


def build_model(name: str, *, random_state: int, n_jobs: int) -> ClassifierMixin:
    """Construct one classifier under an explicit random-state policy."""

    if name == "logistic":
        # Newton-Cholesky is deterministic for a fixed numerical environment and input matrix.
        return LogisticRegression(max_iter=2_000, solver="newton-cholesky")
    if name == "linear_svm":
        # Fix liblinear's internal RNG so this model acts as a low-randomness control.
        return LinearSVC(C=1.0, dual="auto", max_iter=5_000, random_state=0)
    if name == "random_forest":
        return RandomForestClassifier(
            n_estimators=250,
            random_state=random_state,
            n_jobs=n_jobs,
            min_samples_leaf=2,
        )
    if name == "sgd_logistic":
        return SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1.0e-4,
            max_iter=2_000,
            tol=1.0e-4,
            shuffle=True,
            random_state=random_state,
            early_stopping=False,
        )
    raise ValueError(f"Unknown model: {name}")
