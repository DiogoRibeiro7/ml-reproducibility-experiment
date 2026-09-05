"""Verify the completed Adult study's frozen scientific boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parents[1]
IMMUTABLE_RELEASE_REF: Final[str] = "v0.7.1"
IMMUTABLE_RELEASE_API: Final[str] = (
    "https://api.github.com/repos/DiogoRibeiro7/ml-reproducibility-experiment/"
    "releases/tags/v0.7.1"
)
IMMUTABLE_CAPSULE_ASSET: Final[str] = "adult_preregistration_capsule.json"
IMMUTABLE_CAPSULE_URL: Final[str] = (
    "https://github.com/DiogoRibeiro7/ml-reproducibility-experiment/"
    "releases/download/v0.7.1/adult_preregistration_capsule.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return payload


def _load_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    parsed: object = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError(f"Expected JSON object in {label}")
    return parsed


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _request(url: str, *, accept: str) -> bytes:
    headers = {
        "Accept": accept,
        "User-Agent": "ml-reproducibility-change-control",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def _fetch_immutable_capsule() -> tuple[dict[str, Any], str, str]:
    """Fetch the externally immutable v0.7.1 capsule and GitHub-recorded digest."""
    release = _load_json_bytes(
        _request(IMMUTABLE_RELEASE_API, accept="application/vnd.github+json"),
        IMMUTABLE_RELEASE_API,
    )
    if release.get("tag_name") != IMMUTABLE_RELEASE_REF:
        raise ValueError("Immutable release reference resolved to the wrong tag")
    if release.get("immutable") is not True:
        raise ValueError("Frozen release is not marked immutable by GitHub")

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise TypeError("Immutable release metadata has no asset list")
    matching = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name") == IMMUTABLE_CAPSULE_ASSET
    ]
    if len(matching) != 1:
        raise ValueError("Immutable release must contain exactly one preregistration capsule")
    asset = matching[0]
    digest = asset.get("digest")
    download_url = asset.get("browser_download_url")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ValueError("Immutable capsule asset has no GitHub-recorded SHA-256 digest")
    if download_url != IMMUTABLE_CAPSULE_URL:
        raise ValueError("Immutable capsule asset URL is not the frozen expected URL")

    capsule_bytes = _request(IMMUTABLE_CAPSULE_URL, accept="application/octet-stream")
    capsule_sha256 = _sha256_bytes(capsule_bytes)
    if capsule_sha256 != digest.removeprefix("sha256:"):
        raise ValueError("Downloaded immutable capsule disagrees with GitHub asset digest")
    capsule = _load_json_bytes(capsule_bytes, IMMUTABLE_CAPSULE_ASSET)
    return capsule, capsule_sha256, IMMUTABLE_RELEASE_REF


def _safe_locked_path(root: Path, relative_path: str) -> Path:
    """Resolve a frozen path and reject absolute paths or repository escapes."""
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"Frozen path must be relative: {relative_path}")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"Frozen path escapes repository root: {relative_path}")
    return resolved


def verify_against_capsule(
    root: Path,
    *,
    capsule: dict[str, Any],
    capsule_sha256: str,
    immutable_ref: str,
) -> list[str]:
    """Verify one repository tree against an externally anchored capsule."""
    design_lock_path = root / "artifacts" / "adult_design_lock.json"
    local_capsule_path = root / "artifacts" / "adult_preregistration_capsule.json"
    policy_path = root / "governance" / "change_control_policy.json"
    lineage_path = root / "governance" / "lineage_contract.json"

    design_lock = _load_json(design_lock_path)
    policy = _load_json(policy_path)
    lineage = _load_json(lineage_path)

    anchored_design = capsule.get("design_lock")
    anchored_design_sha = capsule.get("design_lock_sha256")
    if not isinstance(anchored_design, dict) or not isinstance(anchored_design_sha, str):
        raise ValueError("Immutable capsule is missing the frozen design identity")

    if _sha256(local_capsule_path) != capsule_sha256:
        raise ValueError("Local preregistration capsule differs from immutable release asset")
    if _sha256(design_lock_path) != anchored_design_sha:
        raise ValueError("Adult design-lock artifact differs from immutable release identity")
    if design_lock != anchored_design:
        raise ValueError("Adult design-lock content differs from immutable preregistration")

    release_identity = policy.get("current_release_identity")
    if not isinstance(release_identity, dict):
        raise TypeError("Change-control policy has no current release identity")
    if release_identity.get("design_lock_sha256") != anchored_design_sha:
        raise ValueError("Change-control policy disagrees with immutable design identity")
    if release_identity.get("preregistration_capsule_sha256") != capsule_sha256:
        raise ValueError("Change-control policy disagrees with immutable capsule identity")
    if release_identity.get("external_anchor_ref") != immutable_ref:
        raise ValueError("Change-control policy disagrees with immutable release reference")

    design_identity = lineage.get("design_identity")
    if not isinstance(design_identity, dict):
        raise TypeError("Lineage contract has no design identity")
    if design_identity.get("design_lock_sha256") != anchored_design_sha:
        raise ValueError("Lineage contract disagrees with immutable design identity")
    if design_identity.get("preregistration_capsule_sha256") != capsule_sha256:
        raise ValueError("Lineage contract disagrees with immutable capsule identity")

    files = anchored_design.get("files_sha256")
    if not isinstance(files, dict) or not files:
        raise ValueError("Immutable design lock has no protected file map")

    verified: list[str] = []
    for relative_path, expected_sha in files.items():
        if not isinstance(relative_path, str) or not isinstance(expected_sha, str):
            raise TypeError("Immutable design lock contains invalid path/hash entries")
        path = _safe_locked_path(root, relative_path)
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


def verify(root: Path = ROOT) -> list[str]:
    """Verify a repository tree against the immutable external release anchor."""
    capsule, capsule_sha256, immutable_ref = _fetch_immutable_capsule()
    return verify_against_capsule(
        root,
        capsule=capsule,
        capsule_sha256=capsule_sha256,
        immutable_ref=immutable_ref,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository tree to verify against the immutable release",
    )
    args = parser.parse_args(argv)
    verified = verify(args.root)
    print(
        f"Adult frozen boundary verified against {IMMUTABLE_RELEASE_REF}: "
        f"{len(verified)} locked files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
