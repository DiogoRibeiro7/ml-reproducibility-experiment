"""Regression tests for governance change control."""

from __future__ import annotations

import json
import runpy
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_change_control.py"
POLICY = ROOT / "governance" / "change_control_policy.json"
DESIGN_LOCK = ROOT / "artifacts" / "adult_design_lock.json"
CAPSULE = ROOT / "artifacts" / "adult_preregistration_capsule.json"
LINEAGE = ROOT / "governance" / "lineage_contract.json"


def _namespace() -> dict[str, object]:
    return runpy.run_path(str(SCRIPT), run_name="change_control_verifier")


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _verify_against_local_capsule(root: Path) -> list[str]:
    namespace = _namespace()
    verifier = cast(
        Callable[..., list[str]],
        namespace["verify_against_capsule"],
    )
    capsule = _load_json(CAPSULE)
    sha256 = cast(Callable[[Path], str], namespace["_sha256"])
    immutable_ref = cast(str, namespace["IMMUTABLE_RELEASE_REF"])
    return verifier(
        root,
        capsule=capsule,
        capsule_sha256=sha256(CAPSULE),
        immutable_ref=immutable_ref,
    )


def _copy_verifier_fixture(destination: Path) -> None:
    """Copy only files needed to exercise frozen-boundary verification."""
    design_lock = _load_json(DESIGN_LOCK)
    required = {
        Path("artifacts/adult_design_lock.json"),
        Path("artifacts/adult_preregistration_capsule.json"),
        Path("governance/change_control_policy.json"),
        Path("governance/lineage_contract.json"),
        *(Path(path) for path in design_lock["files_sha256"]),
    }
    for relative in required:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_current_release_frozen_boundary_is_intact() -> None:
    design_lock = _load_json(DESIGN_LOCK)
    expected = set(design_lock["files_sha256"])
    assert set(_verify_against_local_capsule(ROOT)) == expected


def test_change_control_policy_classifies_frozen_and_governance_changes() -> None:
    policy = _load_json(POLICY)
    scientific = policy["change_classes"]["scientific_specification"]
    governance = policy["change_classes"]["governance_overlay"]

    assert "artifacts/adult_design_lock.json:files_sha256" in scientific["source"]
    assert "governance/" in governance["prefixes"]
    assert "tests/" in governance["prefixes"]
    assert "scripts/" in governance["prefixes"]


def test_modified_frozen_file_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _copy_verifier_fixture(root)
    locked = root / "configs" / "adult.yml"
    locked.write_text(locked.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    try:
        _verify_against_local_capsule(root)
    except ValueError as exc:
        assert "Frozen scientific file drift: configs/adult.yml" in str(exc)
    else:
        raise AssertionError("Modified frozen scientific file was accepted")


def test_rewritten_local_lock_and_policy_cannot_redefine_release(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _copy_verifier_fixture(root)

    locked = root / "configs" / "adult.yml"
    locked.write_text(locked.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    namespace = _namespace()
    sha256 = cast(Callable[[Path], str], namespace["_sha256"])
    design_lock_path = root / "artifacts" / "adult_design_lock.json"
    design_lock = _load_json(design_lock_path)
    design_lock["files_sha256"]["configs/adult.yml"] = sha256(locked)
    design_lock_path.write_text(json.dumps(design_lock, indent=2) + "\n", encoding="utf-8")

    policy_path = root / "governance" / "change_control_policy.json"
    policy = _load_json(policy_path)
    policy["current_release_identity"]["design_lock_sha256"] = sha256(design_lock_path)
    policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

    try:
        _verify_against_local_capsule(root)
    except ValueError as exc:
        assert "immutable release identity" in str(exc) or "immutable preregistration" in str(exc)
    else:
        raise AssertionError("Rewritten local lock redefined the immutable release")


def test_frozen_path_escape_is_rejected(tmp_path: Path) -> None:
    namespace = _namespace()
    safe_path = cast(Callable[[Path, str], Path], namespace["_safe_locked_path"])
    root = tmp_path / "repo"
    root.mkdir()

    try:
        safe_path(root, "../outside.txt")
    except ValueError as exc:
        assert "escapes repository root" in str(exc)
    else:
        raise AssertionError("Repository path escape was accepted")


def test_governance_overlay_is_not_part_of_scientific_lock() -> None:
    design_lock = _load_json(DESIGN_LOCK)
    locked = set(design_lock["files_sha256"])
    assert "governance/change_control_policy.json" not in locked
    assert "scripts/verify_change_control.py" not in locked
    assert "tests/test_change_control.py" not in locked
