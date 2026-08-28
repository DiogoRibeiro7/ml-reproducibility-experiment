# Prospective protocol

## Status

This protocol defines the first primary UCI Adult execution for `v0.5.0`.

No Adult source bytes or Adult model outputs are present in this release. The frozen design must first be represented by a deterministic preregistration capsule and those exact bytes must be published externally before source retrieval.

## Required execution order

```text
prospective design files
        ↓
existing v0.4.0 design lock
        ↓
build-anchor-capsule
        ↓
publish exact capsule bytes as an external release/archive asset
        ↓
record-external-anchor
        ↓
verify-external-anchor
        ↓
download-data
        ↓
run-all
        ↓
release-status
        ↓
full independent replay of all 1196 fits
        ↓
finalise-primary-release
```

The Adult design is already frozen in this release. **Do not run `freeze-design` for Adult.**

## Preregistration capsule

Before any Adult source byte is retrieved, run:

```bash
poetry run ml-repro --root . verify-design-lock --config configs/adult.yml
poetry run ml-repro --root . build-anchor-capsule --config configs/adult.yml
```

This produces:

```text
artifacts/adult_preregistration_capsule.json
artifacts/adult_preregistration_capsule.json.sha256
```

The capsule binds the current design lock, configuration, UCI source-byte policy, models, procedures, tolerances and exact prospective fit counts. Construction is rejected if canonical Adult source bytes or Adult empirical outputs are already present.

## External publication

Publish the **exact capsule file**, without rewriting or reformatting it, as a stable HTTPS object. Suitable examples include a GitHub release asset or a DOI-backed archive file.

Then record the external object using the CLI rather than hand-editing the anchor record:

```bash
poetry run ml-repro --root . record-external-anchor \
  --config configs/adult.yml \
  --kind github_release_asset \
  --url https://github.com/OWNER/REPO/releases/download/v0.4.0/adult_preregistration_capsule.json \
  --immutable-ref v0.4.0
```

Supported kinds are:

- `github_release_asset`;
- `doi_archive_file`;
- `archive_file`.

The URL must use HTTPS. `record-external-anchor` downloads the external object and creates `artifacts/adult_external_anchor.json` only when the remote bytes are identical to the locally generated capsule.

The canonical anchor schema is therefore machine-generated rather than manually asserted. Its fields include the design-lock digest, local capsule digest and independently retrieved remote capsule digest.

A later

```bash
poetry run ml-repro --root . verify-external-anchor --config configs/adult.yml
```

re-fetches the remote object and verifies byte identity again.

## Adult acquisition receipt

`download-data` is available only after successful remote-anchor verification. Its `data/raw/receipt.json` binds:

- the canonical Adult source SHA-256 values;
- the UCI DOI;
- the retrieval timestamp recorded by the execution environment;
- the verified external-anchor identity;
- the local and remote preregistration-capsule hashes.

The receipt is subsequently required by Adult loading and release verification. Every Adult raw-run manifest and the analysis manifest bind the same anchor identity.

## Locked design elements

The design lock binds:

- `configs/adult.yml`;
- this protocol;
- `docs/STUDY_DESIGN.md`;
- `pyproject.toml`;
- `environment/requirements.lock.txt`;
- `environment/runtime-policy.json`;
- every Python source file in `src/ml_reproducibility/`, including the capsule, remote-anchor
  verification and deterministic-serialisation code.

## Runtime policy

The canonical primary environment uses Python 3.13.5, the exact package versions in `environment/requirements.lock.txt`, one estimator job and one numerical thread. Run manifests capture the numerical backend and an environment identity hash. All raw experiment families must have the same environment identity.

### Deterministic serialisation

Every scientific CSV and JSON artifact is written through `src/ml_reproducibility/serialization.py`, which pins LF newlines and the 12-significant-digit float format. Python text mode and `DataFrame.to_csv` otherwise emit the host platform's newline, so identical science produced on Windows and Linux would yield different SHA-256 values and fail the release gate on line endings alone. Byte identity is therefore a property of the experiment, not of the machine.

### Platform binding of behavioural signatures

Aggregate metrics and every derived analysis table are portable across operating systems. The per-fit `prediction_sha256` and `score_sha256` signatures are not: continuous scores differ in their final floating-point bits between BLAS builds. `full_empirical_replay` therefore reproduces exactly only on the canonical platform declared in `environment/runtime-policy.json`.

This is a deliberate strictness, not a defect. A replication attempt on another platform is expected to reproduce all derived tables byte-for-byte while differing in continuous-score signatures, and that outcome must be reported as a platform difference rather than as a failed reproduction or as tampering.

The repository retains Poetry metadata. Because Poetry itself was not available in the isolated build environment used to prepare this release, the exact prospective runtime is additionally represented by the package lock above rather than by a newly generated `poetry.lock`.

## Reference estimands

For every model the reference specification is:

```text
split_seed      = 1729
model_seed      = 2718
preprocessing   = standard
```

For split and seed sensitivity, the reference observation is excluded from reproduction rates. The analysis reports both reference-conditioned and all-pairs reproducibility.

For preprocessing, the alternatives are a fixed finite set and are reported as procedure stability rather than as a sampling probability.

## Crossed designs

The 8 × 8 × 3 crossed design is executed independently for:

- SGD Logistic;
- Random Forest.

This permits split, seed, preprocessing and two-way interaction sensitivity to be assessed without conditioning the stochastic-estimator conclusion on one arbitrary split or one arbitrary seed.

## Convergence policy

Convergence status is recorded for every run. A configured run remains in the analysis if it emits a scikit-learn `ConvergenceWarning`. Such an outcome is reported rather than discarded or rerun with altered hyperparameters.

## Release gate

A primary empirical release is authorised only if all applicable checks pass:

1. prospective design-lock verification;
2. canonical Python/package runtime verification;
3. local preregistration-capsule consistency;
4. exact remote-versus-local capsule byte verification;
5. anchor-bound Adult acquisition-receipt verification;
6. exact prospective run grids for all four result families;
7. raw result and manifest integrity checks, including anchor identity;
8. environment identity consistency across raw families;
9. baseline consistency across overlapping experiment families;
10. deterministic-control invariance under irrelevant seed changes;
11. exact recomputation of every derived table;
12. **independent reconstruction of every configured raw fit**, with metrics agreeing to the declared CSV precision and behavioural/convergence outputs agreeing exactly.

The full-replay requirement means a coordinated modification of a raw CSV, its manifest, behavioural hashes and all derived tables still fails unless the altered result can actually be regenerated by the locked experiment.

## Failure policy

A failed gate means the artifact is not release-ready. The gate must not be weakened after inspecting a primary result merely to obtain a pass.

If a genuine software defect is found after Adult execution begins, document it and create a new version rather than silently changing the locked design.
