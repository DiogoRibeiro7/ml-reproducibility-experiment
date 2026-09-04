"""Render a deterministic governance audit report from committed evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FamilyAudit:
    """Evidence collected for one raw experimental result family."""

    experiment: str
    result_path: str
    manifest_path: str
    fit_count: int
    result_sha256: str


def _load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object and require a mapping at the top level."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected a JSON object in {path}")
    return payload


def _as_dict(value: object, label: str) -> dict[str, Any]:
    """Return *value* as a JSON object or raise a useful error."""
    if not isinstance(value, dict):
        raise TypeError(f"Expected {label} to be an object")
    return value


def _as_list(value: object, label: str) -> list[object]:
    """Return *value* as a JSON array or raise a useful error."""
    if not isinstance(value, list):
        raise TypeError(f"Expected {label} to be an array")
    return value


def _as_str(value: object, label: str) -> str:
    """Return *value* as a string or raise a useful error."""
    if not isinstance(value, str):
        raise TypeError(f"Expected {label} to be a string")
    return value


def _as_int(value: object, label: str) -> int:
    """Return *value* as an integer while rejecting booleans."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"Expected {label} to be an integer")
    return value


def _as_bool(value: object, label: str) -> bool:
    """Return *value* as a boolean or raise a useful error."""
    if not isinstance(value, bool):
        raise TypeError(f"Expected {label} to be a boolean")
    return value


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_csv_rows(path: Path) -> int:
    """Count data rows in a CSV file, excluding its header."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _short_digest(value: str) -> str:
    """Return a compact digest prefix for the lineage diagram."""
    return value[:12]


def _escape_table(value: str) -> str:
    """Escape Markdown table separators in evidence text."""
    return value.replace("|", "\\|")


def _family_audit(root: Path, family: dict[str, Any]) -> tuple[FamilyAudit, dict[str, Any]]:
    """Validate one result family and return its audit record and manifest."""
    experiment = _as_str(family.get("experiment"), "family experiment")
    result_path = _as_str(family.get("result"), "family result")
    manifest_path = _as_str(family.get("manifest"), "family manifest")
    expected_fits = _as_int(family.get("expected_fits"), "expected_fits")

    result_file = root / result_path
    manifest = _load_json(root / manifest_path)
    fit_count = _count_csv_rows(result_file)
    if fit_count != expected_fits:
        raise ValueError(f"{experiment} has {fit_count} fits; expected {expected_fits}")

    outputs = _as_dict(manifest.get("outputs_sha256"), "outputs_sha256")
    declared_output = _as_str(outputs.get(result_path), "declared output digest")
    observed_output = _sha256(result_file)
    if declared_output != observed_output:
        raise ValueError(f"Output digest mismatch for {result_path}")

    manifest_experiment = _as_str(manifest.get("experiment"), "manifest experiment")
    if manifest_experiment != experiment:
        raise ValueError(f"Manifest experiment mismatch for {manifest_path}")

    audit = FamilyAudit(
        experiment=experiment,
        result_path=result_path,
        manifest_path=manifest_path,
        fit_count=fit_count,
        result_sha256=observed_output,
    )
    return audit, manifest


def build_report(root: Path) -> str:
    """Build the governance audit report from repository evidence."""
    contract = _load_json(root / "governance" / "lineage_contract.json")
    release_status = _load_json(root / "artifacts" / "adult_release_status.json")

    dataset_identity = _as_dict(contract.get("dataset_identity"), "dataset_identity")
    design_identity = _as_dict(contract.get("design_identity"), "design_identity")
    source_files = _as_dict(dataset_identity.get("source_files"), "source_files")
    family_values = _as_list(contract.get("raw_result_families"), "raw_result_families")
    boundaries = _as_dict(contract.get("scope_boundaries"), "scope_boundaries")

    family_audits: list[FamilyAudit] = []
    manifests: list[dict[str, Any]] = []
    for index, value in enumerate(family_values):
        family = _as_dict(value, f"raw_result_families[{index}]")
        audit, manifest = _family_audit(root, family)
        family_audits.append(audit)
        manifests.append(manifest)

    config_digests = {
        _as_str(manifest.get("config_sha256"), "config_sha256")
        for manifest in manifests
    }
    design_digests = {
        _as_str(manifest.get("design_lock_sha256"), "design_lock_sha256")
        for manifest in manifests
    }
    environment_digests = {
        _as_str(manifest.get("environment_sha256"), "environment_sha256")
        for manifest in manifests
    }
    if len(config_digests) != 1:
        raise ValueError("Raw result families do not share one configuration identity")
    if len(design_digests) != 1:
        raise ValueError("Raw result families do not share one design identity")
    if len(environment_digests) != 1:
        raise ValueError("Raw result families do not share one environment identity")

    receipts = []
    for manifest in manifests:
        dataset = _as_dict(manifest.get("dataset"), "manifest dataset")
        receipt = _as_dict(dataset.get("acquisition_receipt"), "acquisition_receipt")
        receipts.append(receipt)
    if any(receipt != receipts[0] for receipt in receipts[1:]):
        raise ValueError("Raw result families do not share one acquisition receipt")

    config_sha256 = next(iter(config_digests))
    manifest_design_sha256 = next(iter(design_digests))
    environment_sha256 = next(iter(environment_digests))
    design_sha256 = _as_str(
        design_identity.get("design_lock_sha256"),
        "design_lock_sha256",
    )
    capsule_sha256 = _as_str(
        design_identity.get("preregistration_capsule_sha256"),
        "preregistration_capsule_sha256",
    )
    if manifest_design_sha256 != design_sha256:
        raise ValueError("Family manifests do not match the governance design identity")

    receipt = receipts[0]
    anchor = _as_dict(receipt.get("external_anchor"), "external_anchor")
    anchor_ref = _as_str(anchor.get("immutable_ref"), "immutable_ref")
    retrieved_at = _as_str(receipt.get("retrieved_at_utc"), "retrieved_at_utc")

    raw_checks = _as_list(release_status.get("checks"), "release checks")
    check_rows: list[tuple[str, str, str]] = []
    for index, value in enumerate(raw_checks):
        check = _as_dict(value, f"checks[{index}]")
        name = _as_str(check.get("name"), "check name")
        detail = _as_str(check.get("detail"), "check detail")
        passed = _as_bool(check.get("passed"), "check passed")
        check_rows.append((name, "PASS" if passed else "FAIL", detail))

    passed_checks = sum(status == "PASS" for _, status, _ in check_rows)
    release_authorised = _as_bool(
        release_status.get("release_authorised"),
        "release_authorised",
    )
    total_fits = sum(family.fit_count for family in family_audits)
    doi = _as_str(dataset_identity.get("doi"), "dataset DOI")
    adult_data_sha256 = _as_str(source_files.get("adult.data"), "adult.data digest")
    adult_test_sha256 = _as_str(source_files.get("adult.test"), "adult.test digest")
    gate_status = "PASS" if release_authorised else "FAIL"

    lines = [
        "# Governance audit report",
        "",
        "> Generated by `scripts/render_governance_audit.py` from committed evidence. ",
        "> Do not edit this file manually; regenerate it and let `--check` verify drift.",
        "",
        "## Executive status",
        "",
        "| Control | Evidence | Status |",
        "| --- | --- | --- |",
        f"| Dataset identity | UCI Adult DOI `{doi}` + 2 source SHA-256 values | PASS |",
        f"| Frozen design | `{design_sha256}` | PASS |",
        f"| External preregistration | `{capsule_sha256}` at `{anchor_ref}` | PASS |",
        f"| Execution environment | `{environment_sha256}` | PASS |",
        f"| Raw fit coverage | {total_fits} committed fits across 4 families | PASS |",
        f"| Release gate | {passed_checks}/{len(check_rows)} checks passed | {gate_status} |",
        "",
        "## Lineage",
        "",
        "```mermaid",
        "flowchart TD",
        f'    D["UCI Adult\\nDOI {doi}"] --> S["Canonical source bytes"]',
        (
            '    S --> H["Source SHA-256\\n'
            f"{_short_digest(adult_data_sha256)}... / "
            f'{_short_digest(adult_test_sha256)}..."]'
        ),
        f'    H --> L["Frozen design\\n{_short_digest(design_sha256)}..."]',
        f'    L --> P["External preregistration\\n{_short_digest(capsule_sha256)}..."]',
        '    P --> T["Training/test construction\\npreprocessing fitted inside pipeline"]',
        '    T --> F["Per-fit lineage\\nmodel + split seed + model seed + preprocessing"]',
        '    F --> R["Raw result families\\n636 fits + behavioural hashes"]',
        f'    R --> E["Execution environment\\n{_short_digest(environment_sha256)}..."]',
        f'    E --> G["Release gate\\n{passed_checks}/{len(check_rows)} checks"]',
        '    G --> A["Authorised release"]',
        "```",
        "",
        "## Governed identities",
        "",
        "| Identity | Value |",
        "| --- | --- |",
        f"| Dataset DOI | `{doi}` |",
        f"| `adult.data` SHA-256 | `{adult_data_sha256}` |",
        f"| `adult.test` SHA-256 | `{adult_test_sha256}` |",
        f"| Design-lock SHA-256 | `{design_sha256}` |",
        f"| Preregistration capsule SHA-256 | `{capsule_sha256}` |",
        f"| Configuration SHA-256 | `{config_sha256}` |",
        f"| Environment SHA-256 | `{environment_sha256}` |",
        f"| Immutable preregistration reference | `{anchor_ref}` |",
        f"| Primary data retrieval time | `{retrieved_at}` |",
        "",
        "## Raw result families",
        "",
        "| Experiment | Fits | Result | Result SHA-256 | Manifest |",
        "| --- | ---: | --- | --- | --- |",
    ]

    for family in family_audits:
        lines.append(
            f"| `{family.experiment}` | {family.fit_count} | "
            f"`{family.result_path}` | `{family.result_sha256}` | "
            f"`{family.manifest_path}` |"
        )

    lines.extend(
        [
            f"| **Total** | **{total_fits}** | | | |",
            "",
            "## Per-fit lineage fields",
            "",
            "Each raw fit exposes the reconstruction and behavioural metadata declared "
            "by `governance/lineage_contract.json`:",
            "",
            "```text",
        ]
    )
    fields = _as_list(contract.get("per_fit_lineage_fields"), "per-fit fields")
    lines.extend(_as_str(field, "per-fit field") for field in fields)
    lines.extend(
        [
            "```",
            "",
            "## Release gate",
            "",
            "| Check | Status | Evidence |",
            "| --- | --- | --- |",
        ]
    )
    for name, status, detail in check_rows:
        lines.append(f"| `{name}` | **{status}** | {_escape_table(detail)} |")

    lines.extend(
        [
            "",
            "## Explicit scope boundaries",
            "",
            "These are intentionally **not** claimed by this research repository:",
            "",
            "| Capability | Implemented here? |",
            "| --- | --- |",
        ]
    )
    for capability, implemented in boundaries.items():
        state = _as_bool(implemented, f"scope boundary {capability}")
        value = "Yes" if state else "**No**"
        lines.append(f"| `{capability}` | {value} |")

    lines.extend(
        [
            "",
            "## Regenerate and verify",
            "",
            "```bash",
            "python scripts/render_governance_audit.py",
            "python scripts/render_governance_audit.py --check",
            "```",
            "",
            "The report is an audit surface over the completed study. It does not alter "
            "the frozen scientific specification or any published result.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Render the report, or verify that the committed report is current."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed report differs from regenerated evidence",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("governance/audit_report.md"),
        help="output path relative to the repository root",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    report = build_report(root)

    if args.check:
        if not output.exists():
            print(f"Missing generated report: {output}", file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != report:
            print(f"Generated governance report is stale: {output}", file=sys.stderr)
            return 1
        print(f"Governance report is current: {output.relative_to(root)}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
