"""Platform-independent serialisation regression tests.

Scientific artifacts are compared by SHA-256. If any writer emitted the platform
newline, identical science would produce different bytes on Windows and Linux and the
release gate would fail on line endings alone. These tests pin the byte contract.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from ml_reproducibility.design import freeze_design
from ml_reproducibility.provenance import write_manifest
from ml_reproducibility.serialization import (
    canonical_json_bytes,
    write_csv,
    write_json,
    write_text,
)


def _copy_design_repo(source: Path, destination: Path) -> Path:
    """Create the minimum repository tree required by the lock implementation."""

    for relative in (
        "configs/smoke.yml",
        "docs/PROTOCOL.md",
        "docs/STUDY_DESIGN.md",
        "pyproject.toml",
        "environment/requirements.lock.txt",
        "environment/runtime-policy.json",
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    package = destination / "src" / "ml_reproducibility"
    package.mkdir(parents=True, exist_ok=True)
    for source_file in (source / "src" / "ml_reproducibility").glob("*.py"):
        shutil.copy2(source_file, package / source_file.name)
    return destination / "configs" / "smoke.yml"


def test_write_csv_uses_lf_on_every_platform(tmp_path: Path) -> None:
    """A result table must never contain a carriage return."""

    frame = pd.DataFrame({"model": ["logistic", "linear_svm"], "roc_auc": [0.5, 0.25]})
    destination = tmp_path / "table.csv"
    write_csv(frame, destination)

    payload = destination.read_bytes()
    assert b"\r\n" not in payload
    assert payload == b"model,roc_auc\nlogistic,0.5\nlinear_svm,0.25\n"


def test_write_csv_preserves_twelve_significant_digits(tmp_path: Path) -> None:
    """The canonical CSV precision must survive the deterministic writer."""

    frame = pd.DataFrame({"roc_auc": [0.123456789012345]})
    destination = tmp_path / "precision.csv"
    write_csv(frame, destination)

    assert destination.read_bytes() == b"roc_auc\n0.123456789012\n"


def test_write_json_is_sorted_lf_and_has_no_trailing_newline(tmp_path: Path) -> None:
    """JSON artifacts must be deterministic and byte-stable across platforms."""

    destination = tmp_path / "payload.json"
    write_json(destination, {"b": 2, "a": 1})

    payload = destination.read_bytes()
    assert b"\r" not in payload
    assert payload == b'{\n  "a": 1,\n  "b": 2\n}'
    assert payload == canonical_json_bytes({"a": 1, "b": 2})


def test_write_text_does_not_translate_newlines(tmp_path: Path) -> None:
    """Digest sidecars must keep the exact bytes they declare."""

    destination = tmp_path / "digest.sha256"
    write_text(destination, "abc  file.json\n")

    assert destination.read_bytes() == b"abc  file.json\n"


def test_design_lock_is_written_without_carriage_returns(tmp_path: Path) -> None:
    """The design lock is hashed downstream, so its bytes must be platform-free."""

    source = Path(__file__).resolve().parents[1]
    config = _copy_design_repo(source, tmp_path)
    lock_path = freeze_design(tmp_path, config)

    assert b"\r" not in lock_path.read_bytes()


def test_run_manifest_is_written_without_carriage_returns(tmp_path: Path) -> None:
    """Run manifests bind output hashes and are themselves hashed."""

    source = Path(__file__).resolve().parents[1]
    config = _copy_design_repo(source, tmp_path)
    lock_path = freeze_design(tmp_path, config)

    output = tmp_path / "results" / "smoke" / "split_sensitivity.csv"
    write_csv(pd.DataFrame({"roc_auc": [0.5]}), output)
    destination = tmp_path / "results" / "smoke" / "split_sensitivity.manifest.json"
    write_manifest(
        destination,
        experiment_name="split_sensitivity",
        root=tmp_path,
        config_path=config,
        design_lock=lock_path,
        dataset_provenance={"name": "test"},
        outputs=[output],
        execution_policy={"n_jobs": 1, "numeric_threads": 1},
    )

    payload = destination.read_bytes()
    assert b"\r" not in payload
    assert json.loads(payload.decode("utf-8"))["experiment"] == "split_sensitivity"
