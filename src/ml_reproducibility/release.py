"""Machine-verifiable release gate for the reproducibility study."""

from __future__ import annotations

import importlib.metadata
import json
import math
import platform
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .analysis import METRICS, build_analysis_tables
from .anchor import AnchorEvidence, verify_external_anchor
from .config import ExperimentConfig, load_config
from .data import load_dataset, verify_adult_files, verify_adult_receipt
from .design import verify_design_lock
from .experiment import (
    RunSpec,
    factorial_specs,
    preprocessing_sensitivity_specs,
    run_specs,
    seed_sensitivity_specs,
    split_sensitivity_specs,
)
from .provenance import environment_identity, sha256_bytes, sha256_path
from .serialization import write_csv, write_json

RAW_FAMILIES: dict[str, Callable[[ExperimentConfig], list[RunSpec]]] = {
    "split_sensitivity": split_sensitivity_specs,
    "seed_sensitivity": seed_sensitivity_specs,
    "preprocessing_sensitivity": preprocessing_sensitivity_specs,
    "factorial": factorial_specs,
}
DERIVED_TABLES: tuple[str, ...] = (
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
)
SIGNATURE_COLUMNS: tuple[str, ...] = ("prediction_sha256", "score_sha256")
DIAGNOSTIC_COLUMNS: tuple[str, ...] = (
    "converged",
    "convergence_warning_count",
    "n_iter",
)


@dataclass(frozen=True)
class GateCheck:
    """One release-gate result."""

    name: str
    passed: bool
    detail: str


def _resolve(root: Path, configured: Path) -> Path:
    """Resolve a repository-relative configured path."""

    return configured if configured.is_absolute() else root / configured


def _stable_csv(frame: pd.DataFrame, path: Path) -> None:
    """Write a derived table using the experiment's canonical CSV representation."""

    write_csv(frame, path)


def _spec_tuple(spec: RunSpec) -> tuple[str, str, int, int, str]:
    """Represent a run specification in the same key space as result rows."""

    return (spec.experiment, spec.model, spec.split_seed, spec.model_seed, spec.preprocessing)


def _as_int(value: Any) -> int:
    """Coerce a pandas scalar to a plain Python integer."""

    return int(value)


def _frame_spec_tuples(frame: pd.DataFrame) -> list[tuple[str, str, int, int, str]]:
    """Extract result rows as experiment-specification keys."""

    return [
        (
            str(row.experiment),
            str(row.model),
            _as_int(row.split_seed),
            _as_int(row.model_seed),
            str(row.preprocessing),
        )
        for row in frame.itertuples(index=False)
    ]


def _parse_requirements_lock(path: Path) -> dict[str, str]:
    """Parse the exact package requirements used by the canonical runtime."""

    requirements: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "==" not in stripped:
            raise ValueError(f"Non-exact requirement in {path}: {stripped}")
        name, version = stripped.split("==", maxsplit=1)
        requirements[name] = version
    return requirements


def _verify_reference_environment(root: Path, cfg: ExperimentConfig) -> None:
    """Require the prospectively pinned Python/package/runtime policy."""

    policy_path = root / "environment" / "runtime-policy.json"
    requirements_path = root / "environment" / "requirements.lock.txt"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if platform.python_version() != str(policy.get("python_version")):
        raise ValueError(
            f"Python mismatch: expected {policy.get('python_version')}, "
            f"found {platform.python_version()}"
        )
    if cfg.n_jobs != int(policy.get("n_jobs", -1)):
        raise ValueError("n_jobs does not match the locked runtime policy")
    if cfg.numeric_threads != int(policy.get("numeric_threads", -1)):
        raise ValueError("numeric_threads does not match the locked runtime policy")

    mismatches: list[str] = []
    for package, expected in _parse_requirements_lock(requirements_path).items():
        try:
            observed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            observed = "NOT_INSTALLED"
        if observed != expected:
            mismatches.append(f"{package}: expected {expected}, found {observed}")
    if mismatches:
        raise ValueError("Canonical package environment mismatch: " + "; ".join(mismatches))


def _verify_manifest(
    *,
    root: Path,
    config_path: Path,
    lock_path: Path,
    result_path: Path,
    manifest_path: Path,
    cfg: ExperimentConfig,
    expected_external_anchor: dict[str, object] | None = None,
) -> str:
    """Verify one raw result's provenance manifest and return its environment identity."""

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("config_sha256") != sha256_path(config_path):
        raise ValueError(f"Config hash mismatch in {manifest_path.name}")
    if payload.get("design_lock_sha256") != sha256_path(lock_path):
        raise ValueError(f"Design-lock hash mismatch in {manifest_path.name}")

    outputs = payload.get("outputs_sha256")
    if not isinstance(outputs, dict):
        raise TypeError(f"outputs_sha256 is not a mapping in {manifest_path.name}")
    relative_result = result_path.resolve().relative_to(root.resolve()).as_posix()
    if outputs.get(relative_result) != sha256_path(result_path):
        raise ValueError(f"Output hash mismatch in {manifest_path.name}")

    if expected_external_anchor is not None:
        if payload.get("external_anchor") != expected_external_anchor:
            raise ValueError(f"External-anchor binding mismatch in {manifest_path.name}")
    elif "external_anchor" in payload:
        raise ValueError(f"Unexpected external-anchor binding in {manifest_path.name}")

    policy = payload.get("execution_policy")
    expected_policy = {"n_jobs": cfg.n_jobs, "numeric_threads": cfg.numeric_threads}
    if policy != expected_policy:
        raise ValueError(f"Execution-policy mismatch in {manifest_path.name}")

    environment = payload.get("environment")
    claimed_environment_hash = payload.get("environment_sha256")
    if not isinstance(environment, dict) or not isinstance(claimed_environment_hash, str):
        raise TypeError(f"Missing environment identity in {manifest_path.name}")
    calculated_environment_hash = environment_identity(environment)
    if claimed_environment_hash != calculated_environment_hash:
        raise ValueError(f"Environment hash mismatch in {manifest_path.name}")

    claimed_payload_hash = payload.pop("manifest_payload_sha256", None)
    calculated_payload_hash = sha256_bytes(
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    )
    if claimed_payload_hash != calculated_payload_hash:
        raise ValueError(f"Manifest self-hash mismatch in {manifest_path.name}")
    return claimed_environment_hash


def _verify_raw_family(
    *,
    root: Path,
    result_dir: Path,
    config_path: Path,
    lock_path: Path,
    cfg: ExperimentConfig,
    name: str,
    factory: Callable[[ExperimentConfig], list[RunSpec]],
    expected_external_anchor: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, str]:
    """Verify rows, metrics, diagnostics, signatures and manifest for one result family."""

    result_path = result_dir / f"{name}.csv"
    manifest_path = result_dir / f"{name}.manifest.json"
    if not result_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Missing result family or manifest: {name}")

    frame = pd.read_csv(result_path)
    required = {
        "experiment",
        "model",
        "split_seed",
        "model_seed",
        "preprocessing",
        "n_train",
        "n_test",
        *METRICS,
        *SIGNATURE_COLUMNS,
        *DIAGNOSTIC_COLUMNS,
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {sorted(missing)}")

    expected = sorted(_spec_tuple(spec) for spec in factory(cfg))
    observed = sorted(_frame_spec_tuples(frame))
    if observed != expected:
        raise ValueError(f"{name} does not contain the exact prospective run grid")
    if len(observed) != len(set(observed)):
        raise ValueError(f"{name} contains duplicate run specifications")

    for metric in METRICS:
        values = pd.to_numeric(frame[metric], errors="coerce")
        if values.isna().any() or not values.map(math.isfinite).all():
            raise ValueError(f"{name}.{metric} contains non-finite values")
        if ((values < 0.0) | (values > 1.0)).any():
            raise ValueError(f"{name}.{metric} falls outside [0, 1]")
    for signature in SIGNATURE_COLUMNS:
        if not frame[signature].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
            raise ValueError(f"{name}.{signature} contains invalid SHA-256 values")

    warning_count = pd.to_numeric(frame["convergence_warning_count"], errors="coerce")
    iterations = pd.to_numeric(frame["n_iter"], errors="coerce")
    if warning_count.isna().any() or (warning_count < 0).any():
        raise ValueError(f"{name}.convergence_warning_count is invalid")
    if iterations.isna().any() or (iterations < -1).any():
        raise ValueError(f"{name}.n_iter is invalid")
    converged = frame["converged"].astype(str).str.lower().map({"true": True, "false": False})
    if converged.isna().any():
        raise ValueError(f"{name}.converged is not boolean")
    inconsistent = (warning_count == 0) != converged
    if inconsistent.any():
        raise ValueError(f"{name} has inconsistent convergence diagnostics")

    environment_hash = _verify_manifest(
        root=root,
        config_path=config_path,
        lock_path=lock_path,
        result_path=result_path,
        manifest_path=manifest_path,
        cfg=cfg,
        expected_external_anchor=expected_external_anchor,
    )
    return frame, environment_hash


def _verify_baseline_consistency(
    frames: dict[str, pd.DataFrame], cfg: ExperimentConfig
) -> None:
    """Require overlapping baseline specifications to give identical behaviour."""

    comparable = [
        *METRICS,
        *SIGNATURE_COLUMNS,
        *DIAGNOSTIC_COLUMNS,
        "n_train",
        "n_test",
    ]
    for model in cfg.models:
        rows: list[pd.Series[Any]] = []
        for family in ("split_sensitivity", "seed_sensitivity", "preprocessing_sensitivity"):
            frame = frames[family]
            matches = frame.loc[
                (frame["model"] == model)
                & (frame["split_seed"] == cfg.baseline_split_seed)
                & (frame["model_seed"] == cfg.baseline_model_seed)
                & (frame["preprocessing"] == "standard")
            ]
            if len(matches) != 1:
                raise ValueError(f"Missing unique baseline row for {model} in {family}")
            rows.append(matches.iloc[0])
        first = rows[0]
        for row in rows[1:]:
            if any(row[column] != first[column] for column in comparable):
                raise ValueError(f"Baseline result is inconsistent across families for {model}")

    factorial = frames["factorial"]
    seed = frames["seed_sensitivity"]
    for model in cfg.factorial_models:
        factorial_rows = factorial.loc[
            (factorial["model"] == model)
            & (factorial["split_seed"] == cfg.baseline_split_seed)
            & (factorial["model_seed"] == cfg.baseline_model_seed)
            & (factorial["preprocessing"] == "standard")
        ]
        reference = seed.loc[
            (seed["model"] == model)
            & (seed["split_seed"] == cfg.baseline_split_seed)
            & (seed["model_seed"] == cfg.baseline_model_seed)
            & (seed["preprocessing"] == "standard")
        ]
        if len(factorial_rows) != 1 or len(reference) != 1:
            raise ValueError(f"Missing factorial/reference baseline overlap for {model}")
        if any(
            factorial_rows.iloc[0][column] != reference.iloc[0][column] for column in comparable
        ):
            raise ValueError(f"Factorial baseline disagrees with the main baseline for {model}")


def _verify_deterministic_controls(seed: pd.DataFrame) -> None:
    """Require deterministic controls to be invariant to irrelevant model-seed labels."""

    for model in ("logistic", "linear_svm"):
        subset = seed.loc[seed["model"] == model]
        if subset.empty:
            continue
        for column in (*METRICS, *SIGNATURE_COLUMNS, *DIAGNOSTIC_COLUMNS):
            if subset[column].nunique(dropna=False) != 1:
                raise ValueError(f"Deterministic control {model} varies across seeds in {column}")


def _verify_derived_tables(
    *,
    result_dir: Path,
    frames: dict[str, pd.DataFrame],
    cfg: ExperimentConfig,
) -> None:
    """Recompute all derived tables and require byte-identical stored results."""

    recomputed = build_analysis_tables(
        split=frames["split_sensitivity"],
        seed=frames["seed_sensitivity"],
        preprocess=frames["preprocessing_sensitivity"],
        factorial=frames["factorial"],
        cfg=cfg,
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in DERIVED_TABLES:
            stored = result_dir / f"{name}.csv"
            if not stored.exists():
                raise FileNotFoundError(f"Missing derived table: {stored}")
            candidate = tmp_dir / f"{name}.csv"
            _stable_csv(recomputed[name], candidate)
            if sha256_path(stored) != sha256_path(candidate):
                raise ValueError(f"Derived table does not reproduce exactly: {name}")


def _sorted_family(frame: pd.DataFrame) -> pd.DataFrame:
    """Return raw rows in canonical run-grid order."""

    keys = ["experiment", "model", "split_seed", "model_seed", "preprocessing"]
    return frame.sort_values(keys, kind="stable").reset_index(drop=True)


def _verify_full_empirical_replay(
    *,
    root: Path,
    cfg: ExperimentConfig,
    frames: dict[str, pd.DataFrame],
    expected_external_anchor: dict[str, object] | None = None,
) -> None:
    """Independently reconstruct every raw fit and compare all scientific outputs."""

    bundle = load_dataset(
        cfg.dataset,
        raw_dir=root / "data" / "raw",
        expected_external_anchor=expected_external_anchor,
    )
    exact_columns = [
        "experiment",
        "model",
        "split_seed",
        "model_seed",
        "preprocessing",
        "n_train",
        "n_test",
        *SIGNATURE_COLUMNS,
        *DIAGNOSTIC_COLUMNS,
    ]
    for family, factory in RAW_FAMILIES.items():
        rerun = _sorted_family(run_specs(bundle, cfg, factory(cfg)))
        stored = _sorted_family(frames[family])
        if len(rerun) != len(stored):
            raise ValueError(f"Full replay row-count mismatch for {family}")
        for column in exact_columns:
            if rerun[column].astype(str).tolist() != stored[column].astype(str).tolist():
                raise ValueError(f"Full replay exact mismatch for {family}.{column}")
        for metric in METRICS:
            observed = rerun[metric].to_numpy(dtype=float)
            expected = stored[metric].to_numpy(dtype=float)
            if not all(
                math.isclose(a, b, rel_tol=0.0, abs_tol=1.0e-11)
                for a, b in zip(observed, expected, strict=True)
            ):
                raise ValueError(f"Full replay metric mismatch for {family}.{metric}")


def evaluate_release(
    root: Path, config_path: Path
) -> tuple[list[GateCheck], dict[str, pd.DataFrame]]:
    """Evaluate every release gate and return checks plus verified raw frames."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    result_dir = _resolve(root, cfg.output_dir)
    checks: list[GateCheck] = []
    frames: dict[str, pd.DataFrame] = {}
    anchor_evidence: AnchorEvidence | None = None

    try:
        lock_path = verify_design_lock(root, config_path)
        checks.append(GateCheck("design_lock", True, "prospective design lock verified"))
    except Exception as exc:  # noqa: BLE001 - gate must report every failure
        checks.append(GateCheck("design_lock", False, str(exc)))
        return checks, frames

    try:
        _verify_reference_environment(root, cfg)
        checks.append(GateCheck("reference_environment", True, "canonical runtime verified"))
    except Exception as exc:  # noqa: BLE001
        checks.append(GateCheck("reference_environment", False, str(exc)))

    if cfg.dataset == "adult":
        try:
            anchor_evidence = verify_external_anchor(root, config_path, lock_path)
            checks.append(
                GateCheck(
                    "external_anchor",
                    True,
                    "remote preregistration capsule matches the prospectively locked design",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(GateCheck("external_anchor", False, str(exc)))

    try:
        if cfg.dataset == "adult":
            if anchor_evidence is None:
                raise ValueError(
                    "Adult dataset receipt cannot be verified without the external anchor"
                )
            raw_dir = root / "data" / "raw"
            verify_adult_files(raw_dir)
            verify_adult_receipt(
                raw_dir,
                expected_external_anchor=anchor_evidence.as_manifest_payload(root),
            )
        else:
            load_dataset(cfg.dataset, raw_dir=root / "data" / "raw")
        checks.append(GateCheck("dataset", True, "dataset provenance verified"))
    except Exception as exc:  # noqa: BLE001
        checks.append(GateCheck("dataset", False, str(exc)))

    environment_hashes: set[str] = set()
    for name, factory in RAW_FAMILIES.items():
        try:
            frame, environment_hash = _verify_raw_family(
                root=root,
                result_dir=result_dir,
                config_path=config_path,
                lock_path=lock_path,
                cfg=cfg,
                name=name,
                factory=factory,
                expected_external_anchor=(
                    anchor_evidence.as_manifest_payload(root)
                    if anchor_evidence is not None
                    else None
                ),
            )
            frames[name] = frame
            environment_hashes.add(environment_hash)
            checks.append(GateCheck(f"raw_{name}", True, "exact run grid and manifest verified"))
        except Exception as exc:  # noqa: BLE001
            checks.append(GateCheck(f"raw_{name}", False, str(exc)))

    if len(frames) == len(RAW_FAMILIES):
        try:
            if len(environment_hashes) != 1:
                raise ValueError("Raw experiment families were produced in different environments")
            checks.append(GateCheck("environment_consistency", True, "all raw families agree"))
        except Exception as exc:  # noqa: BLE001
            checks.append(GateCheck("environment_consistency", False, str(exc)))

        validators: tuple[tuple[str, Callable[[], None]], ...] = (
            ("baseline_consistency", lambda: _verify_baseline_consistency(frames, cfg)),
            (
                "deterministic_controls",
                lambda: _verify_deterministic_controls(frames["seed_sensitivity"]),
            ),
            (
                "derived_tables",
                lambda: _verify_derived_tables(result_dir=result_dir, frames=frames, cfg=cfg),
            ),
            (
                "full_empirical_replay",
                lambda: _verify_full_empirical_replay(
                    root=root,
                    cfg=cfg,
                    frames=frames,
                    expected_external_anchor=(
                        anchor_evidence.as_manifest_payload(root)
                        if anchor_evidence is not None
                        else None
                    ),
                ),
            ),
        )
        for name, validator in validators:
            try:
                validator()
                checks.append(GateCheck(name, True, "verified"))
            except Exception as exc:  # noqa: BLE001
                checks.append(GateCheck(name, False, str(exc)))

    return checks, frames


def write_release_status(root: Path, config_path: Path) -> Path:
    """Evaluate the release and write a machine-readable status artifact."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    checks, _ = evaluate_release(root, config_path)
    passed = bool(checks) and all(check.passed for check in checks)
    destination = root / "artifacts" / f"{config_path.stem}_release_status.json"
    payload = {
        "schema": 2,
        "dataset": cfg.dataset,
        "config": config_path.relative_to(root).as_posix(),
        "release_authorised": passed,
        "checks": [asdict(check) for check in checks],
    }
    write_json(destination, payload)
    return destination


def finalise_primary_release(root: Path, config_path: Path) -> Path:
    """Create the empirical release manifest only after every gate passes."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    checks, _ = evaluate_release(root, config_path)
    failures = [check for check in checks if not check.passed]
    if failures:
        detail = "; ".join(f"{check.name}: {check.detail}" for check in failures)
        raise RuntimeError(f"Primary release is not authorised: {detail}")

    result_dir = _resolve(root, cfg.output_dir)
    lock_path = verify_design_lock(root, config_path)
    derived_hashes = {
        f"{name}.csv": sha256_path(result_dir / f"{name}.csv") for name in DERIVED_TABLES
    }
    raw_hashes = {
        f"{name}.csv": sha256_path(result_dir / f"{name}.csv") for name in RAW_FAMILIES
    }
    key_tables = {
        name: pd.read_csv(result_dir / f"{name}.csv").to_dict(orient="records")
        for name in (
            "reproducibility_drift",
            "reference_reproducibility_curve",
            "pairwise_reproducibility_curve",
            "procedure_stability",
            "conditional_split_seed_variability",
            "behavioural_reference_match",
            "factorial_anova_roc_auc",
            "convergence_summary",
        )
    }
    destination = result_dir / "primary_release_manifest.json"
    payload: dict[str, object] = {
        "schema": 3,
        "dataset": cfg.dataset,
        "config_sha256": sha256_path(config_path),
        "design_lock_sha256": sha256_path(lock_path),
        "raw_results_sha256": raw_hashes,
        "derived_results_sha256": derived_hashes,
        "key_results": key_tables,
        "release_gate": [asdict(check) for check in checks],
    }
    if cfg.dataset == "adult":
        anchor_evidence = verify_external_anchor(root, config_path, lock_path)
        payload["external_anchor"] = anchor_evidence.as_manifest_payload(root)
    write_json(destination, payload)
    return destination
