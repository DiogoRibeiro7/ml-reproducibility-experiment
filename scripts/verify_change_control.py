"""Verify the completed Adult study's frozen scientific boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESIGN_LOCK = ROOT / "artifacts" / "adult_design_lock.json"
CHANGE_POLICY = ROOT / "governance" / "change_control_policy.json"
LINEAGE_CONTRACT = ROOT / "governance" / "lineage_contract.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path = ROOT) -> list[str]:
    """Return verified locked paths or raise on scientific-identity drift."""
    design_lock_path = root / "artifacts" / "adult_design_lock.json"
    policy_path = root / "governance" / "change_control_policy.json"
    lineage_path = root / "governance" / "lineage_contract.json"

    design_lock = _load_json(design_lock_path)
    policy = _load_json(policy_path)
    lineage = _load_json(lineage_path)

    release_identity = policy["current_release_identity"]
    expected_design_sha = release_identity["design_lock_sha256"]
    if _sha256(design_lock_path) != expected_design_sha:
        raise ValueError("Adult design-lock artifact no longer matches release identity")

    lineage_design = lineage["design_identity"]["design_lock_sha256"]
    if lineage_design != expected_design_sha:
        raise ValueError("Lineage contract disagrees with the Adult design-lock identity")

    files = design_lock.get("files_sha256")
    if not isinstance(files, dict) or not files:
        raise ValueError("Adult design lock has no protected file map")

    verified: list[str] = []
    for relative_path, expected_sha in files.items():
        if not isinstance(relative_path, str) or not isinstance(expected_sha, str):
            raise TypeError("Adult design lock contains invalid path/hash entries")
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Missing frozen scientific file: {relative_path}")
        observed = _sha256(path)
        if observed != expected_sha:
            raise ValueError(
                f"Frozen scientific file drift: {relative_path}: "
                f"expected {expected_sha}, got {observed}"
            )
        verified.append(relative_path)

    return verified


def main() -> int:
    verified = verify()
    print(f"Adult frozen boundary verified: {len(verified)} locked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
