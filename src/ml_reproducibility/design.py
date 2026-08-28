"""Prospective design locking for empirical execution."""

from __future__ import annotations

import json
from pathlib import Path

from .config import load_config
from .provenance import sha256_path
from .serialization import write_json

LOCK_SCHEMA_VERSION = 2


def design_lock_path(root: Path, config_path: Path) -> Path:
    """Return the canonical lock path for a configuration file."""

    return root / "artifacts" / f"{config_path.stem}_design_lock.json"


def _design_files(root: Path, config_path: Path) -> list[Path]:
    """Return every file whose content determines the prospective experiment."""

    fixed = [
        config_path,
        root / "pyproject.toml",
        root / "docs" / "PROTOCOL.md",
        root / "docs" / "STUDY_DESIGN.md",
        root / "environment" / "requirements.lock.txt",
        root / "environment" / "runtime-policy.json",
    ]
    source = sorted((root / "src" / "ml_reproducibility").glob("*.py"))
    files = fixed + source
    missing = [path for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Cannot freeze design; missing files: {missing}")
    return files


def _relative(root: Path, path: Path) -> str:
    """Return a stable repository-relative path."""

    return path.resolve().relative_to(root.resolve()).as_posix()


def freeze_design(root: Path, config_path: Path, *, overwrite: bool = False) -> Path:
    """Freeze the complete prospective experiment definition into a hash lock."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    destination = design_lock_path(root, config_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Design lock already exists at {destination}. Verify it; do not silently re-freeze."
        )

    files = _design_files(root, config_path)
    payload = {
        "lock_schema": LOCK_SCHEMA_VERSION,
        "dataset": cfg.dataset,
        "config": _relative(root, config_path),
        "files_sha256": {
            _relative(root, path): sha256_path(path)
            for path in sorted(files, key=lambda item: _relative(root, item))
        },
    }
    write_json(destination, payload)
    return destination


def verify_design_lock(root: Path, config_path: Path) -> Path:
    """Verify that no prospectively locked design file has changed."""

    root = root.resolve()
    config_path = config_path.resolve()
    destination = design_lock_path(root, config_path)
    if not destination.exists():
        raise FileNotFoundError(
            f"Missing design lock: {destination}. "
            "Freeze the design before data retrieval/execution."
        )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    if payload.get("lock_schema") != LOCK_SCHEMA_VERSION:
        raise ValueError("Unsupported design-lock schema")
    expected = payload.get("files_sha256")
    if not isinstance(expected, dict):
        raise TypeError("Design lock files_sha256 must be a mapping")

    current_files = _design_files(root, config_path)
    current = {
        _relative(root, path): sha256_path(path)
        for path in sorted(current_files, key=lambda item: _relative(root, item))
    }
    if set(expected) != set(current):
        missing = sorted(set(expected) - set(current))
        added = sorted(set(current) - set(expected))
        raise ValueError(f"Design file set changed; missing={missing}, added={added}")

    drift = [path for path, digest in current.items() if expected.get(path) != digest]
    if drift:
        raise ValueError(f"Prospective design lock mismatch: {drift}")
    return destination
