# ML Reproducibility Experiment

A controlled **classical machine-learning** study of how reported tabular-classification results change because of train/test splitting, estimator randomness and preprocessing choices.

The repository is an empirical experiment, not a generic experiment-tracking framework.

## Research question

A paper may report one number such as

\[
\mathrm{ROC\text{-}AUC}=0.91.
\]

Another researcher can follow the stated method and obtain a different value. This study asks which parts of a conventional classical-ML workflow drive that difference, and whether reproducing an aggregate metric also reproduces the model's actual behaviour.

## Primary dataset

The primary study uses the UCI **Adult** dataset (Becker & Kohavi, 1996; DOI `10.24432/C5XW20`):

- 48,842 observations;
- 14 predictors;
- mixed categorical and integer features;
- missing values;
- binary income target.

The canonical `adult.data` and `adult.test` bytes are SHA-256 pinned. Source-byte drift is a hard failure.

## Models

| Model | Role |
|---|---|
| Logistic Regression | low-randomness control |
| Linear SVM | low-randomness control |
| Random Forest | stochastic estimator |
| SGD Logistic | stochastic, scale-sensitive estimator |

No neural-network or deep-learning model is used.

## Prospective Adult design

The v0.4.0 primary design contains

\[
\boxed{636\text{ classical-ML fits}}.
\]

They comprise:

- 120 split-sensitivity fits;
- 120 estimator-seed-sensitivity fits;
- 12 preprocessing-sensitivity fits;
- 192 crossed SGD Logistic fits;
- 192 crossed Random Forest fits.

The primary metric is ROC-AUC, with predeclared absolute tolerances

\[
0.001,\quad0.005,\quad0.010.
\]

## Reproducibility estimands

For split and estimator-seed reruns, the study reports **reference-conditioned reproducibility**:

\[
R_0(\varepsilon)
=
P(|M-m_0|\le\varepsilon\mid m_0).
\]

The original reference observation is excluded. With 30 configured runs, there are 29 genuine reruns in the denominator.

The study also reports **pairwise reproducibility**:

\[
R_{\mathrm{pair}}(\varepsilon)
=
P(|M_1-M_2|\le\varepsilon),
\]

using every unordered pair of legitimate runs.

Preprocessing is handled differently. `standard`, `robust` and `none` are deliberately selected procedures rather than random draws, so the repository reports a **procedure-stability fraction** instead of describing the finite set as a probability distribution.

## Behavioural reproducibility

Every run stores SHA-256 signatures for the predicted class vector and continuous score vector. On families with a fixed test set, the study distinguishes

\[
\text{similar ROC-AUC}
\neq
\text{same predictions}
\neq
\text{same scores}.
\]

Reference rows do not count as reproductions of themselves.

## Crossed variance design

The full split × model-seed × preprocessing experiment is run for both stochastic estimators:

\[
8\times8\times3
\]

cells for SGD Logistic and the same 192 cells for Random Forest.

This avoids making the split-versus-seed conclusion depend on one arbitrarily selected baseline split or seed.

## Convergence is data

Every fit records:

```text
converged
convergence_warning_count
n_iter
```

A configured run is not discarded because it fails to converge. For a scale-sensitive method such as SGD, convergence failure under one preprocessing procedure is itself part of the procedural-reproducibility result.

## Numerical execution policy

The canonical primary run fixes:

```text
Python              3.13.5
n_jobs              1
numeric_threads     1
```

Exact package versions live in `environment/requirements.lock.txt`. Model fitting uses `threadpoolctl` to constrain numerical kernels to one thread. Run manifests record the numerical backend and an environment identity hash.

Poetry remains the project metadata/tooling convention. Because Poetry was unavailable in the isolated build environment used to prepare the locked runtime, the prospective package set is additionally pinned through the explicit requirements lock rather than a newly generated `poetry.lock`.

## Machine-verifiable preregistration capsule

v0.4.0 strengthens the prospective boundary. A local JSON that merely claims to point at a release is no longer sufficient.

After the Adult design has been frozen, the command

```bash
poetry run ml-repro --root . build-anchor-capsule --config configs/adult.yml
```

creates

```text
artifacts/adult_preregistration_capsule.json
artifacts/adult_preregistration_capsule.json.sha256
```

The capsule is deterministic and contains:

- the complete design-lock payload and its SHA-256;
- the configuration SHA-256;
- the pinned UCI source URLs and source-byte hashes;
- the model and preprocessing sets;
- the primary metric and reproduction tolerances;
- the exact raw-family fit counts and 636-fit total;
- explicit assertions that Adult source bytes and Adult empirical outputs were absent when capsule construction was authorised.

Capsule construction fails if canonical Adult source files or Adult empirical outputs are already present.

## External publication boundary

The **exact capsule bytes** must then be published through a stable external object such as a GitHub release asset or DOI-backed archive file.

Do not hand-create `adult_external_anchor.json`. Record it with:

```bash
poetry run ml-repro --root . record-external-anchor \
  --config configs/adult.yml \
  --kind github_release_asset \
  --url https://github.com/OWNER/REPO/releases/download/v0.4.0/adult_preregistration_capsule.json \
  --immutable-ref v0.4.0
```

The command retrieves the remote object and refuses to create the local anchor unless

\[
\boxed{
\text{remote capsule bytes}
=
\text{local prospectively generated capsule bytes}.
}
\]

The supported anchor kinds are `github_release_asset`, `doi_archive_file` and `archive_file`. The URL must use HTTPS.

A subsequent

```bash
poetry run ml-repro --root . verify-external-anchor --config configs/adult.yml
```

re-fetches the external capsule and checks the same byte-level identity before Adult execution is authorised.

## Adult acquisition is anchor-bound

Only after the remote capsule verifies may Adult be downloaded:

```bash
poetry run ml-repro --root . download-data --config configs/adult.yml
```

The acquisition receipt binds the raw source hashes to the verified external anchor. Every Adult run manifest and the final empirical release manifest bind the same anchor identity.

Therefore changing the local external-anchor record after empirical execution invalidates the provenance chain.

## Required primary execution order

The repository contains a v0.4.0 Adult design lock. **Do not re-freeze it.**

```text
locked v0.4.0 design
        ↓
build deterministic preregistration capsule
        ↓
publish exact capsule bytes externally
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
full independent replay of all 636 fits
        ↓
finalise-primary-release
```

The executable sequence after publication is:

```bash
poetry run ml-repro --root . verify-design-lock --config configs/adult.yml
poetry run ml-repro --root . verify-external-anchor --config configs/adult.yml
poetry run ml-repro --root . download-data --config configs/adult.yml
poetry run ml-repro --root . run-all --config configs/adult.yml
poetry run ml-repro --root . release-status --config configs/adult.yml
poetry run ml-repro --root . finalise-primary-release --config configs/adult.yml
```

`download-data` and every Adult model-execution command fail when the external anchor is absent, stale or byte-inconsistent with the published capsule.

## Main result artifacts

After a successful primary run:

```text
results/adult/
├── split_sensitivity.csv
├── seed_sensitivity.csv
├── preprocessing_sensitivity.csv
├── factorial.csv
├── split_summary.csv
├── seed_summary.csv
├── preprocessing_summary.csv
├── reproducibility_drift.csv
├── reference_reproducibility_curve.csv
├── pairwise_reproducibility_curve.csv
├── procedure_stability.csv
├── conditional_split_seed_variability.csv
├── behavioural_reference_match.csv
├── factorial_anova_roc_auc.csv
├── convergence_summary.csv
├── analysis.manifest.json
└── primary_release_manifest.json
```

Every raw family has its own provenance manifest.

## Release gate

The release gate verifies the locked design, canonical runtime, remotely reproduced Adult preregistration capsule, anchor-bound source acquisition receipt, exact run grids, manifests, environment consistency, baseline overlaps, deterministic controls and every derived table.

Most importantly, it independently reruns every configured raw fit and requires the proposed raw results to regenerate. Metrics are compared at the declared 12-significant-digit storage precision. Prediction hashes, score hashes and convergence diagnostics must match exactly.

Therefore

\[
\boxed{
\text{edited raw CSV}
+
\text{edited manifest}
+
\text{edited derived tables}
\not\Rightarrow
\text{release pass}
}
\]

unless the altered result can actually be reproduced by the locked experiment.

## Offline validation profile

`configs/smoke.yml` uses scikit-learn's Wisconsin breast-cancer dataset to validate the complete experiment machinery without being confused with the primary Adult result.

```bash
poetry run ml-repro --root . verify-design-lock --config configs/smoke.yml
poetry run ml-repro --root . run-all --config configs/smoke.yml
poetry run ml-repro --root . release-status --config configs/smoke.yml
```

Smoke artifacts live under `results/smoke/`.

## Development

```bash
poetry run ruff check .
poetry run mypy src
poetry run pytest
```

The isolated validation environment can also run the source tree directly with `PYTHONPATH=src`.

See [Study design](docs/STUDY_DESIGN.md) and [Prospective protocol](docs/PROTOCOL.md).

## Current status

`v0.4.0` is a **pre-Adult empirical release**. The canonical Adult source bytes and Adult model results are intentionally absent. The design is frozen and the deterministic preregistration capsule is included locally, but primary execution remains blocked until those exact capsule bytes are published externally and verified.
