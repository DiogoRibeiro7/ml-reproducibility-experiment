"""Environment, hashing and run-manifest capture."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Iterable

from threadpoolctl import threadpool_info

PACKAGES: tuple[str, ...] = (
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "statsmodels",
    "matplotlib",
    "PyYAML",
    "joblib",
    "threadpoolctl",
    "patsy",
)


def sha256_bytes(payload: bytes) -> str:
    """Hash an in-memory byte sequence."""

    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    """Hash a file in streaming chunks."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_versions(packages: Iterable[str] = PACKAGES) -> dict[str, str]:
    """Return installed distribution versions, including missing-state markers."""

    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "NOT_INSTALLED"
    return versions


def _normalised_threadpools() -> list[dict[str, object]]:
    """Return numerical backend identity without machine-specific library paths."""

    entries: list[dict[str, object]] = []
    for item in threadpool_info():
        entries.append(
            {
                key: item.get(key)
                for key in (
                    "user_api",
                    "internal_api",
                    "num_threads",
                    "version",
                    "threading_layer",
                    "architecture",
                )
            }
        )
    return sorted(entries, key=lambda entry: json.dumps(entry, sort_keys=True, default=str))


def environment_manifest() -> dict[str, object]:
    """Capture software and numerical-backend state relevant to reproducibility."""

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": package_versions(),
        "thread_environment": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "threadpools": _normalised_threadpools(),
        "python_executable": sys.executable,
    }


def environment_identity(environment: dict[str, object] | None = None) -> str:
    """Hash the canonical environment fields, excluding executable location."""

    payload = dict(environment_manifest() if environment is None else environment)
    payload.pop("python_executable", None)
    return sha256_bytes(json.dumps(payload, sort_keys=True, default=str).encode("utf-8"))


def write_manifest(
    destination: Path,
    *,
    experiment_name: str,
    root: Path,
    config_path: Path,
    design_lock: Path,
    dataset_provenance: dict[str, object],
    outputs: Iterable[Path],
    execution_policy: dict[str, object] | None = None,
    external_anchor: dict[str, object] | None = None,
) -> None:
    """Write a provenance manifest binding design, data, environment and outputs."""

    root = root.resolve()
    output_hashes = {
        path.resolve().relative_to(root).as_posix(): sha256_path(path)
        for path in outputs
        if path.exists() and path.is_file()
    }
    environment = environment_manifest()
    manifest = {
        "experiment": experiment_name,
        "config_path": config_path.resolve().relative_to(root).as_posix(),
        "config_sha256": sha256_path(config_path),
        "design_lock_path": design_lock.resolve().relative_to(root).as_posix(),
        "design_lock_sha256": sha256_path(design_lock),
        "dataset": dataset_provenance,
        "environment": environment,
        "environment_sha256": environment_identity(environment),
        "execution_policy": execution_policy or {},
        "outputs_sha256": output_hashes,
    }
    if external_anchor is not None:
        manifest["external_anchor"] = external_anchor
    payload = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    manifest["manifest_payload_sha256"] = sha256_bytes(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
