"""Dataset acquisition, verification and parsing."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer

ADULT_DOI: Final[str] = "10.24432/C5XW20"
ADULT_COLUMNS: Final[tuple[str, ...]] = (
    "age",
    "workclass",
    "fnlwgt",
    "education",
    "education_num",
    "marital_status",
    "occupation",
    "relationship",
    "race",
    "sex",
    "capital_gain",
    "capital_loss",
    "hours_per_week",
    "native_country",
    "income",
)

# Canonical UCI byte hashes. Any source-byte drift is a hard failure.
ADULT_FILES: Final[dict[str, tuple[str, str]]] = {
    "adult.data": (
        "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data",
        "5b00264637dbfec36bdeaab5676b0b309ff9eb788d63554ca0a249491c86603d",
    ),
    "adult.test": (
        "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test",
        "a2a9044bc167a35b2361efbabec64e89d69ce82d9790d2980119aac5fd7e9c05",
    ),
}


@dataclass(frozen=True)
class DatasetBundle:
    """Features, labels and provenance for a classification dataset."""

    X: pd.DataFrame
    y: pd.Series
    provenance: dict[str, object]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for *path*."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_adult_files(raw_dir: Path) -> dict[str, str]:
    """Verify that all canonical Adult source files exist with the pinned hashes."""

    observed: dict[str, str] = {}
    for filename, (_, expected_sha256) in ADULT_FILES.items():
        source = raw_dir / filename
        if not source.exists():
            raise FileNotFoundError(f"Missing canonical Adult source file: {source}")
        actual_sha256 = sha256_file(source)
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"Hash mismatch for {filename}: expected {expected_sha256}, got {actual_sha256}"
            )
        observed[filename] = actual_sha256
    return observed


def download_adult(
    raw_dir: Path, *, external_anchor: dict[str, object]
) -> dict[str, str]:
    """Download Adult only after receiving verified external-anchor provenance."""

    required_anchor_fields = {
        "anchor_sha256",
        "capsule_sha256",
        "remote_capsule_sha256",
        "kind",
        "url",
        "immutable_ref",
    }
    missing_anchor = required_anchor_fields - set(external_anchor)
    if missing_anchor:
        raise ValueError(
            f"Verified external-anchor provenance is incomplete: {sorted(missing_anchor)}"
        )

    raw_dir.mkdir(parents=True, exist_ok=True)
    for filename, (url, _) in ADULT_FILES.items():
        destination = raw_dir / filename
        if not destination.exists():
            urllib.request.urlretrieve(url, destination)  # noqa: S310 - fixed trusted URLs

    observed = verify_adult_files(raw_dir)
    receipt = {
        "schema": 2,
        "dataset": "UCI Adult",
        "doi": ADULT_DOI,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": observed,
        "external_anchor": external_anchor,
    }
    (raw_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8"
    )
    return observed


def verify_adult_receipt(
    raw_dir: Path, *, expected_external_anchor: dict[str, object]
) -> dict[str, object]:
    """Verify the Adult acquisition receipt and its prospective-anchor binding."""

    receipt_path = raw_dir / "receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"Missing Adult acquisition receipt: {receipt_path}")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Adult acquisition receipt must be a mapping")
    if payload.get("schema") != 2:
        raise ValueError("Unsupported Adult acquisition-receipt schema")
    if payload.get("dataset") != "UCI Adult" or payload.get("doi") != ADULT_DOI:
        raise ValueError("Adult acquisition receipt dataset identity is invalid")
    if payload.get("files") != verify_adult_files(raw_dir):
        raise ValueError("Adult acquisition receipt does not bind the canonical source bytes")
    if payload.get("external_anchor") != expected_external_anchor:
        raise ValueError("Adult acquisition receipt does not bind the verified external anchor")
    retrieved_at = payload.get("retrieved_at_utc")
    if not isinstance(retrieved_at, str) or not retrieved_at.strip():
        raise ValueError("Adult acquisition receipt is missing retrieved_at_utc")
    return payload


def _read_adult_part(path: Path, *, test: bool) -> pd.DataFrame:
    """Read one canonical UCI Adult source file."""

    frame = pd.read_csv(
        path,
        names=list(ADULT_COLUMNS),
        skipinitialspace=True,
        na_values="?",
        comment="|" if test else None,
        skip_blank_lines=True,
    )
    frame["income"] = frame["income"].astype("string").str.rstrip(".")
    return frame


def load_adult(
    raw_dir: Path, *, expected_external_anchor: dict[str, object] | None = None
) -> DatasetBundle:
    """Load Adult after verifying raw bytes and, when supplied, the acquisition receipt."""

    observed = verify_adult_files(raw_dir)
    receipt: dict[str, object] | None = None
    if expected_external_anchor is not None:
        receipt = verify_adult_receipt(
            raw_dir, expected_external_anchor=expected_external_anchor
        )
    train = _read_adult_part(raw_dir / "adult.data", test=False)
    test = _read_adult_part(raw_dir / "adult.test", test=True)
    frame = pd.concat([train, test], axis=0, ignore_index=True)

    y = frame.pop("income").map({"<=50K": 0, ">50K": 1})
    if y.isna().any():
        unknown = sorted(frame.loc[y.isna()].index.astype(str).tolist()[:5])
        raise ValueError(f"Unrecognised target values at rows: {unknown}")
    y = y.astype("int8")

    return DatasetBundle(
        X=frame,
        y=y,
        provenance={
            "name": "UCI Adult",
            "doi": ADULT_DOI,
            "n_rows": int(frame.shape[0]),
            "n_features": int(frame.shape[1]),
            "raw_sha256": observed,
            "acquisition_receipt": receipt,
        },
    )


def load_breast_cancer_smoke() -> DatasetBundle:
    """Load scikit-learn's bundled Wisconsin diagnostic dataset for offline smoke tests."""

    bunch = load_breast_cancer(as_frame=True)
    if bunch.frame is None or bunch.target is None:
        raise RuntimeError("scikit-learn did not return a framed breast-cancer dataset")

    X = bunch.frame.drop(columns=["target"]).copy()
    y = pd.Series(np.asarray(bunch.target, dtype=np.int8), index=X.index, name="target")
    payload = np.ascontiguousarray(X.to_numpy(dtype=np.float64)).tobytes() + np.ascontiguousarray(
        y.to_numpy(dtype=np.int8)
    ).tobytes()
    digest = hashlib.sha256(payload).hexdigest()

    return DatasetBundle(
        X=X,
        y=y,
        provenance={
            "name": "scikit-learn breast_cancer smoke dataset",
            "n_rows": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "canonical_array_sha256": digest,
        },
    )


def load_dataset(
    name: str,
    *,
    raw_dir: Path,
    expected_external_anchor: dict[str, object] | None = None,
) -> DatasetBundle:
    """Load the requested dataset by name."""

    if name == "adult":
        return load_adult(raw_dir, expected_external_anchor=expected_external_anchor)
    if name == "breast_cancer":
        return load_breast_cancer_smoke()
    raise ValueError(f"Unsupported dataset: {name}")
