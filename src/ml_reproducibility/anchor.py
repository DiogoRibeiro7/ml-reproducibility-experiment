"""Machine-verifiable prospective anchoring for the primary Adult study."""

from __future__ import annotations

import json
import os
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
from .final_lock import final_lock_path
from .provenance import sha256_bytes, sha256_path
from .serialization import write_text

CAPSULE_SCHEMA_VERSION: Final[int] = 1
EXTERNAL_ANCHOR_SCHEMA_VERSION: Final[int] = 3
MAX_REMOTE_CAPSULE_BYTES: Final[int] = 2 * 1024 * 1024
ALLOWED_EXTERNAL_KINDS: Final[frozenset[str]] = frozenset(
    {
        "github_release_asset",
        "github_private_release_asset",
        "doi_archive_file",
        "archive_file",
    }
)
# Kinds whose object cannot be retrieved by an unauthenticated third party. The anchor
# records this so the provenance chain states its own evidential limit rather than
# implying an independent verifiability it does not have.
NON_PUBLIC_KINDS: Final[frozenset[str]] = frozenset({"github_private_release_asset"})
GITHUB_API_VERSION: Final[str] = "2022-11-28"
TOKEN_ENVIRONMENT_VARIABLES: Final[tuple[str, ...]] = ("GITHUB_TOKEN", "GH_TOKEN")


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
    asset_name: str | None
    publicly_retrievable: bool

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
            "asset_name": self.asset_name,
            "publicly_retrievable": self.publicly_retrievable,
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

    # The capsule is the object that gets published, so it carries the readable
    # specification rather than only the digest of the files that encode it.
    final_lock = final_lock_path(root, config_path)
    if not final_lock.exists():
        raise FileNotFoundError(
            f"Missing final experiment lock: {final_lock}. "
            "Build it before the preregistration capsule."
        )
    final_lock_payload = json.loads(final_lock.read_text(encoding="utf-8"))
    if not isinstance(final_lock_payload, dict):
        raise TypeError("Final experiment lock payload must be a mapping")
    if final_lock_payload.get("design_lock_sha256") != sha256_path(lock_path):
        raise ValueError("Final experiment lock does not bind the current design lock")

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
        "final_experiment_lock_sha256": sha256_path(final_lock),
        "final_experiment_lock": final_lock_payload,
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
    write_text(digest_path, f"{sha256_path(destination)}  {destination.name}\n")
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

    final_lock = final_lock_path(root, config_path)
    if not final_lock.exists():
        raise FileNotFoundError(f"Missing final experiment lock: {final_lock}")
    if payload.get("final_experiment_lock_sha256") != sha256_path(final_lock):
        raise ValueError("Preregistration capsule does not bind the final experiment lock")

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

    parsed = urllib.parse.urlparse(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]

    if kind == "github_release_asset":
        if parsed.netloc.lower() != "github.com":
            raise ValueError("github_release_asset must use a github.com release-download URL")
        if len(parts) < 6 or parts[2:4] != ["releases", "download"]:
            raise ValueError(
                "github_release_asset URL must point to /releases/download/<ref>/<asset>"
            )
        if parts[4] != immutable_ref:
            raise ValueError("GitHub release URL tag does not match immutable_ref")
        return

    if kind == "github_private_release_asset":
        if parsed.netloc.lower() != "api.github.com":
            raise ValueError(
                "github_private_release_asset must use an api.github.com release URL"
            )
        if len(parts) != 6 or parts[0] != "repos" or parts[3] != "releases":
            raise ValueError(
                "github_private_release_asset URL must point to "
                "/repos/<owner>/<repo>/releases/tags/<ref>"
            )
        if parts[4] != "tags":
            raise ValueError("github_private_release_asset URL must address a tagged release")
        if parts[5] != immutable_ref:
            raise ValueError("GitHub release tag does not match immutable_ref")
        return


class _StripAuthorizationOnRedirect(urllib.request.HTTPRedirectHandler):
    """Drop the Authorization header when a redirect leaves the API host.

    GitHub answers an asset download with a redirect to a pre-signed storage URL that
    rejects requests still carrying an API token. Forwarding the header, which urllib
    does by default, therefore fails the download and would also leak the credential to
    the storage host.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Return the redirected request without its Authorization header."""

        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


def _read_bounded(response: object) -> bytes:
    """Read a bounded response body."""

    payload: bytes = response.read(MAX_REMOTE_CAPSULE_BYTES + 1)  # type: ignore[attr-defined]
    if len(payload) > MAX_REMOTE_CAPSULE_BYTES:
        raise ValueError("Remote preregistration capsule exceeds the maximum allowed size")
    return payload


def _github_token() -> str:
    """Return the API token used to read a private release, or fail loudly."""

    for name in TOKEN_ENVIRONMENT_VARIABLES:
        token = os.environ.get(name, "").strip()
        if token:
            return token
    raise ValueError(
        "A private release anchor requires an API token in one of "
        f"{list(TOKEN_ENVIRONMENT_VARIABLES)}. The token is used only to retrieve the "
        "published capsule and is never recorded in the anchor."
    )


def _fetch_remote_bytes(url: str) -> bytes:
    """Retrieve a bounded remote capsule over anonymous HTTPS."""

    _validate_https_url(url)
    request = urllib.request.Request(  # noqa: S310 - HTTPS is validated above
        url,
        headers={"User-Agent": f"ml-reproducibility-experiment/{__version__}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        _validate_https_url(str(response.geturl()))
        return _read_bounded(response)


def _fetch_private_github_asset(*, url: str, asset_name: str) -> bytes:
    """Retrieve a capsule published as an asset of a private GitHub release.

    Two requests are needed: the release is resolved by its immutable tag, and the asset
    is then downloaded by its API URL. Only an authenticated caller can do either, which
    is precisely the property that makes this anchor weaker than a public one.
    """

    _validate_https_url(url)
    token = _github_token()
    headers = {
        "User-Agent": f"ml-reproducibility-experiment/{__version__}",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    release_request = urllib.request.Request(  # noqa: S310 - HTTPS is validated above
        url, headers={**headers, "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(release_request, timeout=30) as response:  # noqa: S310
        release = json.loads(_read_bounded(response).decode("utf-8"))
    if not isinstance(release, dict):
        raise TypeError("GitHub release response must be a mapping")

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise TypeError("GitHub release response does not list assets")
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name") == asset_name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one release asset named {asset_name}, found {len(matches)}"
        )
    asset_url = matches[0].get("url")
    if not isinstance(asset_url, str):
        raise TypeError("Release asset is missing its API url")
    _validate_https_url(asset_url)

    opener = urllib.request.build_opener(_StripAuthorizationOnRedirect())
    asset_request = urllib.request.Request(  # noqa: S310 - HTTPS is validated above
        asset_url, headers={**headers, "Accept": "application/octet-stream"}
    )
    with opener.open(asset_request, timeout=30) as response:
        _validate_https_url(str(response.geturl()))
        return _read_bounded(response)


def _retrieve_capsule_bytes(*, kind: str, url: str, asset_name: str | None) -> bytes:
    """Retrieve the published capsule using the mechanism the anchor kind requires."""

    if kind == "github_private_release_asset":
        if not asset_name:
            raise ValueError("github_private_release_asset requires asset_name")
        return _fetch_private_github_asset(url=url, asset_name=asset_name)
    return _fetch_remote_bytes(url)


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
    asset_name: str | None = None,
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

    if kind in NON_PUBLIC_KINDS and not (asset_name or "").strip():
        raise ValueError(f"{kind} requires --asset-name")

    lock_path = verify_design_lock(root, config_path)
    local_capsule = verify_local_capsule(root, config_path)
    remote_bytes = _retrieve_capsule_bytes(kind=kind, url=url, asset_name=asset_name)
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
        "asset_name": (asset_name or None),
        # Recorded, not inferred at read time: a reader of the provenance chain must be
        # able to see whether the preregistration could be checked by anyone but its author.
        "publicly_retrievable": kind not in NON_PUBLIC_KINDS,
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
    asset_name = payload.get("asset_name")
    if not isinstance(kind, str) or kind not in ALLOWED_EXTERNAL_KINDS:
        raise ValueError("External anchor kind is invalid")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("External anchor requires a non-empty url")
    if not isinstance(immutable_ref, str) or not immutable_ref.strip():
        raise ValueError("External anchor requires a non-empty immutable_ref")
    if asset_name is not None and not isinstance(asset_name, str):
        raise TypeError("External anchor asset_name must be a string when present")
    expected_public = kind not in NON_PUBLIC_KINDS
    if payload.get("publicly_retrievable") != expected_public:
        raise ValueError("External anchor misstates whether the capsule is publicly retrievable")
    if kind in NON_PUBLIC_KINDS and not (asset_name or "").strip():
        raise ValueError("A private release anchor must record its asset_name")
    _validate_https_url(url)
    _validate_kind_reference(kind=kind, url=url, immutable_ref=immutable_ref)

    local_capsule_digest = sha256_path(local_capsule)
    if payload.get("design_lock_sha256") != sha256_path(lock_path):
        raise ValueError("External anchor does not bind the current design lock")
    if payload.get("capsule_sha256") != local_capsule_digest:
        raise ValueError("External anchor does not bind the local preregistration capsule")

    remote_bytes = _retrieve_capsule_bytes(kind=kind, url=url, asset_name=asset_name)
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
        asset_name=asset_name,
        publicly_retrievable=expected_public,
    )
