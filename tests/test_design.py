"""Prospective design-lock tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ml_reproducibility.design import freeze_design, verify_design_lock


def _copy_design_repo(source: Path, destination: Path) -> Path:
    """Create the minimum repository tree required by the lock implementation."""

    (destination / "configs").mkdir(parents=True)
    (destination / "docs").mkdir(parents=True)
    (destination / "src" / "ml_reproducibility").mkdir(parents=True)
    (destination / "environment").mkdir(parents=True)
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
    for source_file in (source / "src" / "ml_reproducibility").glob("*.py"):
        shutil.copy2(source_file, destination / "src" / "ml_reproducibility" / source_file.name)
    return destination / "configs" / "smoke.yml"


def test_design_lock_detects_source_drift(tmp_path: Path) -> None:
    """A changed locked source file must invalidate empirical execution."""

    source = Path(__file__).resolve().parents[1]
    config = _copy_design_repo(source, tmp_path)
    freeze_design(tmp_path, config)
    verify_design_lock(tmp_path, config)

    target = tmp_path / "src" / "ml_reproducibility" / "metrics.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    with pytest.raises(ValueError, match="design lock mismatch"):
        verify_design_lock(tmp_path, config)
