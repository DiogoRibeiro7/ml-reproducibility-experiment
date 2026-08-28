"""Prospective preregistration-anchor tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ml_reproducibility import anchor as anchor_module
from ml_reproducibility.anchor import (
    build_preregistration_capsule,
    record_external_anchor,
    verify_external_anchor,
    verify_local_capsule,
)
from ml_reproducibility.design import freeze_design, verify_design_lock


def _copy_adult_design_repo(source: Path, destination: Path) -> Path:
    """Create a complete temporary design tree for Adult anchor tests."""

    for relative in (
        "configs/adult.yml",
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
    return destination / "configs" / "adult.yml"


def test_capsule_binds_locked_adult_design_before_data(tmp_path: Path) -> None:
    """The deterministic capsule must encode the complete 636-fit pre-data design."""

    source = Path(__file__).resolve().parents[1]
    config = _copy_adult_design_repo(source, tmp_path)
    freeze_design(tmp_path, config)

    capsule = build_preregistration_capsule(tmp_path, config)
    assert verify_local_capsule(tmp_path, config) == capsule
    payload = json.loads(capsule.read_text(encoding="utf-8"))
    assert payload["expected_raw_fit_count"] == 636
    assert payload["predata_assertions"] == {
        "adult_empirical_outputs_present_when_capsule_built": False,
        "adult_source_bytes_present_when_capsule_built": False,
    }


def test_capsule_refuses_post_data_construction(tmp_path: Path) -> None:
    """A capsule cannot be freshly created after any Adult source file appears."""

    source = Path(__file__).resolve().parents[1]
    config = _copy_adult_design_repo(source, tmp_path)
    freeze_design(tmp_path, config)
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "adult.data").write_text("already observed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source bytes are present"):
        build_preregistration_capsule(tmp_path, config)


def test_remote_anchor_requires_exact_published_capsule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A remote URL cannot unlock Adult unless its bytes equal the local capsule exactly."""

    source = Path(__file__).resolve().parents[1]
    config = _copy_adult_design_repo(source, tmp_path)
    lock = freeze_design(tmp_path, config)
    capsule = build_preregistration_capsule(tmp_path, config)
    canonical = capsule.read_bytes()

    monkeypatch.setattr(anchor_module, "_fetch_remote_bytes", lambda _: canonical)
    record_external_anchor(
        tmp_path,
        config,
        kind="github_release_asset",
        url=(
            "https://github.com/example/repo/releases/download/"
            "v0.4.0/adult_preregistration_capsule.json"
        ),
        immutable_ref="v0.4.0",
    )
    evidence = verify_external_anchor(tmp_path, config, verify_design_lock(tmp_path, config))
    assert evidence.capsule_sha256 == anchor_module.sha256_path(capsule)

    monkeypatch.setattr(anchor_module, "_fetch_remote_bytes", lambda _: canonical + b" ")
    with pytest.raises(ValueError, match="Remote preregistration capsule bytes"):
        verify_external_anchor(tmp_path, config, lock)


def test_external_anchor_rejects_non_https_url() -> None:
    """Local/file URLs cannot serve as prospective publication evidence."""

    with pytest.raises(ValueError, match="HTTPS"):
        anchor_module._validate_https_url("file:///tmp/capsule.json")


def test_github_anchor_ref_must_match_release_url() -> None:
    """The claimed immutable GitHub ref must be the tag encoded in the asset URL."""

    with pytest.raises(ValueError, match="does not match immutable_ref"):
        anchor_module._validate_kind_reference(
            kind="github_release_asset",
            url=(
                "https://github.com/example/repo/releases/download/"
                "v0.4.0/adult_preregistration_capsule.json"
            ),
            immutable_ref="v9.9.9",
        )
