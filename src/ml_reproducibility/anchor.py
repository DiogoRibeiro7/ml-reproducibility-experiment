"""Machine-verifiable prospective anchoring for the primary Adult study."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from . import __version__
from .config import ExperimentConfig, load_config
from .data import ADULT_DOI, ADULT_FILES
from .design import verify_design_lock
from .experiment import (
    factorial_specs,
    preprocessing_sensitivity_specs,
    seed_sensitivity_specs,
    split_sensitivity_specs,
)
from .provenance import sha256_bytes, sha256_path

CAPSULE_SCHEMA_VERSION: Final[int] = 1
EXTERNAL_ANCHOR_SCHEMA_VERSION: Final[int] = 2
MAX_REMOTE_CAPSULE_BYTES: Final[int] = 2 * 1024 * 1024
ALLOWED_EXTERNAL_KINDS: Final[frozenset[str]] = frozenset(
    {"github_release_asset", "doi_archive_file", "archive_file"}
)


@dataclass(frozen=True)
class AnchorEvidence:
    """Verified local and remote evidence for one prospective anchor."""

    anchor_path: Path
    anchor_sha256: str
    capsule_path: Path
    capsule_sha256: str
    remote_capsule_sha256: str
    kind: str
    url: str
    immutable_ref: str

    def as_manifest_payload(self, root: Path) -> dict[str, object]:
        """Return a stable repository-relative representation for run manifests."""

        return {
            "anchor_path": self.anchor_path.resolve().relative_to(root.resolve()).as_posix(),
            "anchor_sha256": self.anchor_sha256,
            "capsule_path": self.capsule_path.resolve().relative_to(root.resolve()).as_posix(),
            "capsule_sha256": self.capsule_sha256,
            "remote_capsule_sha256": self.remote_capsule_sha256,
            "kind": self.kind,
            "url": self.url,
            "immutable_ref": self.immutable_ref,
        }


def capsule_path(root: Path, config_path: Path) -> Path:
    """Return the canonical preregistration-capsule path."""

    return root / "artifacts" / f"{config_path.stem}_preregistration_capsule.json"


def external_anchor_path(root: Path, config_path: Path) -> Path:
    """Return the canonical local external-anchor record path."""

    return root / "artifacts" / f"{config_path.stem}_external_anchor.json"


def _canonical_json(payload: dict[str, object]) -> bytes:
    """Serialise JSON deterministically while keeping it human-readable."""

    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _relative(root: Path, path: Path) -> str:
    """Return a repository-relative POSIX path."""

    return path.resolve().relative_to(root.resolve()).as_posix()


def _fit_counts(cfg: ExperimentConfig) -> dict[str, int]:
    """Return the exact prospective raw-fit count for every experiment family."""

    return {
        "split_sensitivity": len(split_sensitivity_specs(cfg)),
        "seed_sensitivity": len(seed_sensitivity_specs(cfg)),
        "preprocessing_sensitivity": len(preprocessing_sensitivity_specs(cfg)),
        "factorial": len(factorial_specs(cfg)),
    }


def _assert_preregistration_state(root: Path, cfg: ExperimentConfig) -> None:
    """Require absence of primary Adult source bytes and empirical model outputs."""

    raw_dir = root / "data" / "raw"
    present_sources = [filename for filename in ADULT_FILES if (raw_dir / filename).exists()]
    if present_sources:
        raise ValueError(
            "Cannot build a prospective capsule after Adult source bytes are present: "
            f"{sorted(present_sources)}"
        )

    result_dir = cfg.output_dir if cfg.output_dir.is_absolute() else root / cfg.output_dir
    empirical_files: list[str] = []
    if result_dir.exists():
        for path in sorted(result_dir.glob("*")):
            if path.is_file() and path.suffix.lower() in {".csv", ".json"}:
                empirical_files.append(_relative(root, path))
    primary_manifest = root / "results" / "primary_release_manifest.json"
    if primary_manifest.exists():
        empirical_files.append(_relative(root, primary_manifest))
    if empirical_files:
        raise ValueError(
            "Cannot build a prospective capsule after Adult empirical outputs are present: "
            f"{empirical_files}"
        )


def build_preregistration_capsule(root: Path, config_path: Path) -> Path:
    """Create a deterministic pre-data capsule bound to the verified design lock."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    if cfg.dataset != "adult":
        raise ValueError("The external preregistration capsule is defined only for Adult")

    lock_path = verify_design_lock(root, config_path)
    _assert_preregistration_state(root, cfg)
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(lock_payload, dict):
        raise TypeError("Design-lock payload must be a mapping")

    counts = _fit_counts(cfg)
    payload: dict[str, object] = {
        "capsule_schema": CAPSULE_SCHEMA_VERSION,
        "study": "ml-reproducibility-experiment",
        "software_version": __version__,
        "dataset": "UCI Adult",
        "dataset_doi": ADULT_DOI,
        "config_path": _relative(root, config_path),
        "config_sha256": sha256_path(config_path),
        "design_lock_path": _relative(root, lock_path),
        "design_lock_sha256": sha256_path(lock_path),
        "design_lock": lock_payload,
        "source_policy": {
            filename: {"url": url, "sha256": digest}
            for filename, (url, digest) in sorted(ADULT_FILES.items())
        },
        "primary_metric": cfg.primary_metric,
        "reproducibility_tolerances": list(cfg.reproducibility_tolerances),
        "models": list(cfg.models),
        "factorial_models": list(cfg.factorial_models),
        "preprocessing": list(cfg.preprocessing),
        "raw_family_fit_counts": counts,
        "expected_raw_fit_count": sum(counts.values()),
        "predata_assertions": {
            "adult_source_bytes_present_when_capsule_built": False,
            "adult_empirical_outputs_present_when_capsule_built": False,
        },
    }
    destination = capsule_path(root, config_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_canonical_json(payload))
    digest_path = destination.with_suffix(destination.suffix + ".sha256")
    digest_path.write_text(f"{sha256_path(destination)}  {destination.name}\n", encoding="utf-8")
    return destination


def verify_local_capsule(root: Path, config_path: Path) -> Path:
    """Verify that the stored capsule exactly represents the current locked design."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    lock_path = verify_design_lock(root, config_path)
    path = capsule_path(root, config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing preregistration capsule: {path}. Build it before external publication."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Preregistration capsule must be a mapping")
    if payload.get("capsule_schema") != CAPSULE_SCHEMA_VERSION:
        raise ValueError("Unsupported preregistration-capsule schema")
    if payload.get("software_version") != __version__:
        raise ValueError("Preregistration capsule software version mismatch")
    if payload.get("config_sha256") != sha256_path(config_path):
        raise ValueError("Preregistration capsule does not bind the current configuration")
    if payload.get("design_lock_sha256") != sha256_path(lock_path):
        raise ValueError("Preregistration capsule does not bind the current design lock")

    expected_counts = _fit_counts(cfg)
    if payload.get("raw_family_fit_counts") != expected_counts:
        raise ValueError("Preregistration capsule raw-family fit counts have drifted")
    if payload.get("expected_raw_fit_count") != sum(expected_counts.values()):
        raise ValueError("Preregistration capsule total fit count is inconsistent")

    source_policy = payload.get("source_policy")
    expected_source_policy = {
        filename: {"url": url, "sha256": digest}
        for filename, (url, digest) in sorted(ADULT_FILES.items())
    }
    if source_policy != expected_source_policy:
        raise ValueError("Preregistration capsule Adult source policy has drifted")

    digest_path = path.with_suffix(path.suffix + ".sha256")
    if not digest_path.exists():
        raise FileNotFoundError(f"Missing capsule digest file: {digest_path}")
    fields = digest_path.read_text(encoding="utf-8").strip().split()
    if len(fields) < 1 or fields[0] != sha256_path(path):
        raise ValueError("Preregistration capsule digest file does not match capsule bytes")
    return path


def _validate_https_url(url: str) -> None:
    """Reject local, credential-bearing and non-HTTPS anchor URLs."""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("External anchor URL must be an absolute HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("External anchor URL must not embed credentials")


def _validate_kind_reference(*, kind: str, url: str, immutable_ref: str) -> None:
    """Require provider-specific immutable references to agree with the published URL."""

    if kind != "github_release_asset":
        return
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError("github_release_asset must use a github.com release-download URL")
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 6 or parts[2:4] != ["releases", "download"]:
        raise ValueError("github_release_asset URL must point to /releases/download/<ref>/<asset>")
    if parts[4] != immutable_ref:
        raise ValueError("GitHub release URL tag does not match immutable_ref")


def _fetch_remote_bytes(url: str) -> bytes:
    """Retrieve a bounded remote capsule over HTTPS."""

    _validate_https_url(url)
    request = urllib.request.Request(  # noqa: S310 - HTTPS is validated above
        url,
        headers={"User-Agent": f"ml-reproducibility-experiment/{__version__}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        _validate_https_url(str(response.geturl()))
        payload = response.read(MAX_REMOTE_CAPSULE_BYTES + 1)
    if len(payload) > MAX_REMOTE_CAPSULE_BYTES:
        raise ValueError("Remote preregistration capsule exceeds the maximum allowed size")
    return payload


def _verify_remote_capsule_payload(
    *, remote_bytes: bytes, local_capsule: Path, lock_path: Path, config_path: Path
) -> str:
    """Require remote bytes to equal the local capsule and bind the same locked design."""

    local_bytes = local_capsule.read_bytes()
    if remote_bytes != local_bytes:
        raise ValueError("Remote preregistration capsule bytes do not match the local capsule")
    try:
        payload = json.loads(remote_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Remote preregistration capsule is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Remote preregistration capsule must be a mapping")
    if payload.get("design_lock_sha256") != sha256_path(lock_path):
        raise ValueError("Remote preregistration capsule does not bind the current design lock")
    if payload.get("config_sha256") != sha256_path(config_path):
        raise ValueError("Remote preregistration capsule does not bind the current configuration")
    return sha256_bytes(remote_bytes)


def record_external_anchor(
    root: Path,
    config_path: Path,
    *,
    kind: str,
    url: str,
    immutable_ref: str,
) -> Path:
    """Verify a published capsule remotely, then record the external anchor locally."""

    root = root.resolve()
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    if cfg.dataset != "adult":
        raise ValueError("External anchors are required only for the Adult primary study")
    if kind not in ALLOWED_EXTERNAL_KINDS:
        raise ValueError(f"Unsupported external anchor kind: {kind}")
    if not immutable_ref.strip():
        raise ValueError("immutable_ref must be non-empty")
    _validate_https_url(url)
    _validate_kind_reference(kind=kind, url=url, immutable_ref=immutable_ref.strip())

    lock_path = verify_design_lock(root, config_path)
    local_capsule = verify_local_capsule(root, config_path)
    remote_bytes = _fetch_remote_bytes(url)
    remote_digest = _verify_remote_capsule_payload(
        remote_bytes=remote_bytes,
        local_capsule=local_capsule,
        lock_path=lock_path,
        config_path=config_path,
    )

    destination = external_anchor_path(root, config_path)
    if destination.exists():
        raise FileExistsError(
            f"External anchor already exists at {destination}. "
            "Do not overwrite an established anchor."
        )
    payload: dict[str, object] = {
        "schema": EXTERNAL_ANCHOR_SCHEMA_VERSION,
        "kind": kind,
        "url": url,
        "immutable_ref": immutable_ref.strip(),
        "design_lock_sha256": sha256_path(lock_path),
        "capsule_sha256": sha256_path(local_capsule),
        "remote_capsule_sha256": remote_digest,
    }
    destination.write_bytes(_canonical_json(payload))
    return destination


def verify_external_anchor(root: Path, config_path: Path, lock_path: Path) -> AnchorEvidence:
    """Verify the local anchor record and exact remote preregistration bytes."""

    root = root.resolve()
    config_path = config_path.resolve()
    local_capsule = verify_local_capsule(root, config_path)
    if sha256_path(lock_path) != sha256_path(verify_design_lock(root, config_path)):
        raise ValueError("Provided design lock is not the canonical verified design lock")

    anchor = external_anchor_path(root, config_path)
    if not anchor.exists():
        raise FileNotFoundError(
            f"Missing external prospective anchor: {anchor}. Publish the preregistration "
            "capsule before retrieving Adult data."
        )
    payload = json.loads(anchor.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("External anchor must be a mapping")
    if payload.get("schema") != EXTERNAL_ANCHOR_SCHEMA_VERSION:
        raise ValueError("Unsupported external-anchor schema")

    kind = payload.get("kind")
    url = payload.get("url")
    immutable_ref = payload.get("immutable_ref")
    if not isinstance(kind, str) or kind not in ALLOWED_EXTERNAL_KINDS:
        raise ValueError("External anchor kind is invalid")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("External anchor requires a non-empty url")
    if not isinstance(immutable_ref, str) or not immutable_ref.strip():
        raise ValueError("External anchor requires a non-empty immutable_ref")
    _validate_https_url(url)
    _validate_kind_reference(kind=kind, url=url, immutable_ref=immutable_ref)

    local_capsule_digest = sha256_path(local_capsule)
    if payload.get("design_lock_sha256") != sha256_path(lock_path):
        raise ValueError("External anchor does not bind the current design lock")
    if payload.get("capsule_sha256") != local_capsule_digest:
        raise ValueError("External anchor does not bind the local preregistration capsule")

    remote_bytes = _fetch_remote_bytes(url)
    remote_digest = _verify_remote_capsule_payload(
        remote_bytes=remote_bytes,
        local_capsule=local_capsule,
        lock_path=lock_path,
        config_path=config_path,
    )
    if payload.get("remote_capsule_sha256") != remote_digest:
        raise ValueError("External anchor remote-capsule digest mismatch")

    return AnchorEvidence(
        anchor_path=anchor,
        anchor_sha256=sha256_path(anchor),
        capsule_path=local_capsule,
        capsule_sha256=local_capsule_digest,
        remote_capsule_sha256=remote_digest,
        kind=kind,
        url=url,
        immutable_ref=immutable_ref,
    )
