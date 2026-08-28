"""Command-line interface for the classical-ML reproducibility experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from .analysis import (
    build_analysis_tables,
    plot_anova,
    plot_distributions,
    plot_reference_reproducibility_curve,
)
from .anchor import (
    ALLOWED_EXTERNAL_KINDS,
    build_preregistration_capsule,
    record_external_anchor,
    verify_external_anchor,
)
from .config import ExperimentConfig, load_config
from .data import download_adult, load_dataset
from .design import freeze_design, verify_design_lock
from .experiment import (
    RunSpec,
    factorial_specs,
    preprocessing_sensitivity_specs,
    run_specs,
    save_frame,
    seed_sensitivity_specs,
    split_sensitivity_specs,
)
from .provenance import write_manifest
from .release import finalise_primary_release, write_release_status


def _resolve(root: Path, configured: Path) -> Path:
    """Resolve one repository-relative configured path."""

    return configured if configured.is_absolute() else root / configured


def _execution_policy(cfg: ExperimentConfig) -> dict[str, object]:
    """Return the canonical execution policy bound into every run manifest."""

    return {"n_jobs": cfg.n_jobs, "numeric_threads": cfg.numeric_threads}


def _execute(
    cfg: ExperimentConfig,
    *,
    root: Path,
    config_path: Path,
    name: str,
    spec_factory: Callable[[ExperimentConfig], list[RunSpec]],
) -> Path:
    """Execute one configured experiment family under the prospective design lock."""

    lock_path = verify_design_lock(root, config_path)
    external_anchor: dict[str, object] | None = None
    if cfg.dataset == "adult":
        anchor_evidence = verify_external_anchor(root, config_path, lock_path)
        external_anchor = anchor_evidence.as_manifest_payload(root)
    raw_dir = root / "data" / "raw"
    bundle = load_dataset(
        cfg.dataset,
        raw_dir=raw_dir,
        expected_external_anchor=external_anchor,
    )
    result_dir = _resolve(root, cfg.output_dir)

    frame = run_specs(bundle, cfg, spec_factory(cfg))
    output = result_dir / f"{name}.csv"
    save_frame(frame, output)
    write_manifest(
        result_dir / f"{name}.manifest.json",
        experiment_name=name,
        root=root,
        config_path=config_path,
        design_lock=lock_path,
        dataset_provenance=bundle.provenance,
        outputs=[output],
        execution_policy=_execution_policy(cfg),
        external_anchor=external_anchor,
    )
    return output


def _analyse(cfg: ExperimentConfig, *, root: Path, config_path: Path) -> None:
    """Recompute all summaries, reproducibility diagnostics and figures."""

    lock_path = verify_design_lock(root, config_path)
    external_anchor: dict[str, object] | None = None
    if cfg.dataset == "adult":
        anchor_evidence = verify_external_anchor(root, config_path, lock_path)
        external_anchor = anchor_evidence.as_manifest_payload(root)
    result_dir = _resolve(root, cfg.output_dir)
    figure_dir = _resolve(root, cfg.figure_dir)
    split = pd.read_csv(result_dir / "split_sensitivity.csv")
    seed = pd.read_csv(result_dir / "seed_sensitivity.csv")
    preprocess = pd.read_csv(result_dir / "preprocessing_sensitivity.csv")
    factorial = pd.read_csv(result_dir / "factorial.csv")

    tables = build_analysis_tables(
        split=split,
        seed=seed,
        preprocess=preprocess,
        factorial=factorial,
        cfg=cfg,
    )
    outputs: list[Path] = []
    for name, table in tables.items():
        output = result_dir / f"{name}.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(output, index=False, float_format="%.12g")
        outputs.append(output)

    plot_distributions(
        split,
        factor="train/test split",
        metric=cfg.primary_metric,
        output=figure_dir / "split_roc_auc.png",
    )
    plot_distributions(
        seed,
        factor="model seed",
        metric=cfg.primary_metric,
        output=figure_dir / "seed_roc_auc.png",
    )
    plot_anova(tables["factorial_anova_roc_auc"], output=figure_dir / "factorial_variance.png")
    plot_reference_reproducibility_curve(
        tables["reference_reproducibility_curve"],
        experiment="split_sensitivity",
        output=figure_dir / "split_reference_reproducibility_curve.png",
    )
    plot_reference_reproducibility_curve(
        tables["reference_reproducibility_curve"],
        experiment="seed_sensitivity",
        output=figure_dir / "seed_reference_reproducibility_curve.png",
    )

    bundle = load_dataset(
        cfg.dataset,
        raw_dir=root / "data" / "raw",
        expected_external_anchor=external_anchor,
    )
    write_manifest(
        result_dir / "analysis.manifest.json",
        experiment_name="analysis",
        root=root,
        config_path=config_path,
        design_lock=lock_path,
        dataset_provenance=bundle.provenance,
        outputs=outputs,
        execution_policy=_execution_policy(cfg),
        external_anchor=external_anchor,
    )


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    """Add the standard required configuration argument."""

    parser.add_argument("--config", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("freeze-design", "Create a prospective design lock during design development"),
        ("verify-design-lock", "Verify the existing prospective design lock"),
        ("build-anchor-capsule", "Build the deterministic pre-data preregistration capsule"),
        ("verify-external-anchor", "Verify the published remote preregistration capsule"),
        ("download-data", "Download and verify UCI Adult after the external design anchor"),
        ("analyse", "Recompute all derived analysis outputs"),
        ("release-status", "Evaluate and write the empirical release gate"),
        ("finalise-primary-release", "Create the final release manifest after all gates pass"),
    ):
        sub = subparsers.add_parser(command, help=help_text)
        _add_config_argument(sub)

    record = subparsers.add_parser(
        "record-external-anchor",
        help="Verify remotely published capsule bytes and record the immutable reference",
    )
    _add_config_argument(record)
    record.add_argument("--kind", choices=sorted(ALLOWED_EXTERNAL_KINDS), required=True)
    record.add_argument("--url", required=True)
    record.add_argument("--immutable-ref", required=True)

    for command in (
        "split-sensitivity",
        "seed-sensitivity",
        "preprocessing-sensitivity",
        "factorial",
        "run-all",
    ):
        sub = subparsers.add_parser(command)
        _add_config_argument(sub)
    return parser


def main() -> None:
    """Run the CLI."""

    args = build_parser().parse_args()
    root = args.root.resolve()
    config_path = args.config.resolve()

    if args.command == "freeze-design":
        freeze_design(root, config_path)
        return
    if args.command == "verify-design-lock":
        verify_design_lock(root, config_path)
        return
    if args.command == "build-anchor-capsule":
        build_preregistration_capsule(root, config_path)
        return
    if args.command == "record-external-anchor":
        record_external_anchor(
            root,
            config_path,
            kind=args.kind,
            url=args.url,
            immutable_ref=args.immutable_ref,
        )
        return
    if args.command == "verify-external-anchor":
        lock_path = verify_design_lock(root, config_path)
        verify_external_anchor(root, config_path, lock_path)
        return

    cfg = load_config(config_path)
    if args.command == "download-data":
        lock_path = verify_design_lock(root, config_path)
        if cfg.dataset != "adult":
            raise ValueError("download-data is only defined for the UCI Adult primary dataset")
        anchor_evidence = verify_external_anchor(root, config_path, lock_path)
        download_adult(
            root / "data" / "raw",
            external_anchor=anchor_evidence.as_manifest_payload(root),
        )
        return
    if args.command == "analyse":
        _analyse(cfg, root=root, config_path=config_path)
        return
    if args.command == "release-status":
        status_path = write_release_status(root, config_path)
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if not bool(status.get("release_authorised", False)):
            raise RuntimeError(f"Release gate failed; inspect {status_path}")
        return
    if args.command == "finalise-primary-release":
        finalise_primary_release(root, config_path)
        return

    factories: dict[str, tuple[str, Callable[[ExperimentConfig], list[RunSpec]]]] = {
        "split-sensitivity": ("split_sensitivity", split_sensitivity_specs),
        "seed-sensitivity": ("seed_sensitivity", seed_sensitivity_specs),
        "preprocessing-sensitivity": (
            "preprocessing_sensitivity",
            preprocessing_sensitivity_specs,
        ),
        "factorial": ("factorial", factorial_specs),
    }

    if args.command == "run-all":
        for name, factory in factories.values():
            _execute(cfg, root=root, config_path=config_path, name=name, spec_factory=factory)
        _analyse(cfg, root=root, config_path=config_path)
        return

    name, factory = factories[args.command]
    _execute(cfg, root=root, config_path=config_path, name=name, spec_factory=factory)


if __name__ == "__main__":
    main()
