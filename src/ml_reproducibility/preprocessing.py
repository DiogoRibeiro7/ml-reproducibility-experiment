"""Classical tabular preprocessing pipelines."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler, StandardScaler


def infer_columns(X: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return numeric and categorical column names."""

    numeric = X.select_dtypes(include=["number"]).columns.astype(str).tolist()
    categorical = [str(column) for column in X.columns if str(column) not in numeric]
    return numeric, categorical


def build_preprocessor(
    X: pd.DataFrame,
    *,
    variant: str,
) -> ColumnTransformer:
    """Build a leakage-safe preprocessing transformer.

    The returned transformer must be placed inside a scikit-learn ``Pipeline`` so
    all fitted preprocessing statistics are estimated on the training fold only.
    """

    numeric_columns, categorical_columns = infer_columns(X)

    if variant == "standard":
        numeric_steps: list[tuple[str, object]] = [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    elif variant == "robust":
        numeric_steps = [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]
    elif variant == "none":
        numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    else:
        raise ValueError(f"Unknown preprocessing variant: {variant}")

    transformers: list[tuple[str, object, Sequence[str]]] = []
    if numeric_columns:
        transformers.append(("numeric", Pipeline(numeric_steps), numeric_columns))
    if categorical_columns:
        categorical_pipeline = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="most_frequent")),
                (
                    "onehot",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=True),
                ),
            ]
        )
        transformers.append(("categorical", categorical_pipeline, categorical_columns))

    return ColumnTransformer(transformers=transformers, remainder="drop")
