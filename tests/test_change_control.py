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


def _verify(root: Path) -> list[str]:
    namespace = runpy.run_path(str(SCRIPT), run_name="change_control_verifier")
    verifier = cast(Callable[[Path], list[str]], namespace["verify"])
    return verifier(root)


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_current_release_frozen_boundary_is_intact() -> None:
    design_lock = _load_json(DESIGN_LOCK)
    expected = set(design_lock["files_sha256"])
    assert set(_verify(ROOT)) == expected


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
    shutil.copytree(ROOT, root)
    locked = root / "configs" / "adult.yml"
    locked.write_text(locked.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    try:
        _verify(root)
    except ValueError as exc:
        assert "Frozen scientific file drift: configs/adult.yml" in str(exc)
    else:
        raise AssertionError("Modified frozen scientific file was accepted")


def test_governance_overlay_is_not_part_of_scientific_lock() -> None:
    design_lock = _load_json(DESIGN_LOCK)
    locked = set(design_lock["files_sha256"])
    assert "governance/change_control_policy.json" not in locked
    assert "scripts/verify_change_control.py" not in locked
    assert "tests/test_change_control.py" not in locked
