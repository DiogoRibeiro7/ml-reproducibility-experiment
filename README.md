# ML Reproducibility Experiment

A prospectively frozen, externally preregistered study of what actually reproduces when a
conventional classical machine-learning result is repeated.

**Headline finding: reproducing a reported metric does not reproduce the model.** Across 29
estimator-seed reruns with the test set held fixed, a random forest reproduced its reference
ROC-AUC in **29 of 29** cases at the tightest declared tolerance — while producing a
different prediction vector **every single time**. Exact behavioural match rate: **0.000**.

A replication that checked only the headline number would have reported success in all 29.

---

## Status

The study is complete. The design was frozen and published before any Adult byte was
retrieved; the 636 fits were then executed and independently replayed.

```text
frozen design         v0.7.1  ->  30a0aec3e79c4ddd35c58e284185d702711b205a
adult design lock     2eb2351f4ae40971a5428c7aa6bbf3f906826ade0f99054abd56e03e3275d7d9
preregistration       8d791b1626d524822c0f72c7190353dcf5553cdee3918b57a81d89d33a06c0be
release gate          14 / 14 passed, release_authorised = true
primary fits          636, all independently reconstructed
```

## Verify the preregistration yourself

You do not have to trust any code in this repository. The capsule is an asset of an
immutable public release, and it fixes the entire design:

```bash
curl -fsSL https://github.com/DiogoRibeiro7/ml-reproducibility-experiment/releases/download/v0.7.1/adult_preregistration_capsule.json \
  | sha256sum
# 8d791b1626d524822c0f72c7190353dcf5553cdee3918b57a81d89d33a06c0be
```

The capsule embeds the complete final experiment lock — estimator hyperparameters, the
enumerated seed grids, the train/test procedure, the convergence policy, the statistical
analysis and the release-gate criteria — so it can be **read as a specification**, not
merely hashed. It also asserts that no Adult source byte and no Adult result existed when it
was built.

---

## What the study asked

A paper reports `ROC-AUC = 0.91`. Someone follows the stated method and gets something else.
Which part of an ordinary tabular workflow moved the number — and if the number does come
back, has anything actually been reproduced?

**Design.** UCI Adult (48,842 rows, 14 predictors, source bytes SHA-256 pinned). Four
estimators: logistic regression and a linear SVM as low-randomness controls, a random forest
and an SGD logistic classifier as stochastic estimators. Three preprocessing procedures:
median imputation with standard scaling, with robust scaling, and without scaling.

```text
120  split-sensitivity fits        30 split seeds  × 4 models
120  estimator-seed fits           30 model seeds  × 4 models
 12  preprocessing fits             3 procedures   × 4 models
384  crossed factorial fits         8 × 8 × 3      × 2 stochastic models
───
636  primary model fits
```

No neural networks. The point is a conventional workflow, not a competitive one.

## What it found

### Metric agreement is not behavioural agreement

| estimator | ROC-AUC reproduced at ε=0.001 | distinct prediction vectors | exact match |
|---|---|---|---|
| random_forest | 29 / 29 | 30 / 30 | **0.000** |
| sgd_logistic | 27 / 29 | 30 / 30 | **0.000** |
| logistic *(deterministic)* | 29 / 29 | 1 / 30 | 1.000 |
| linear_svm *(deterministic)* | 29 / 29 | 1 / 30 | 1.000 |

The two deterministic estimators reproduce by construction, not as a finding; every row for
them is flagged `deterministic_by_construction` so a rate of 1.0 is never read as an estimate.

### Where the variance lives depends entirely on the estimator

Share of ROC-AUC sum of squares in the crossed design:

| | split_seed | model_seed | preprocessing |
|---|---|---|---|
| random_forest | **98.9%** | 0.1% | 0.0% |
| sgd_logistic | 0.5% | 0.8% | **87.2%** |

Answering this from a one-factor-at-a-time experiment on one arbitrary baseline would have
generalised badly to the other estimator. That is what the crossed design prevents.

### The convergence flag reports perfect health, and is wrong

All **636 / 636** fits converged. Zero convergence warnings in the entire study. Yet:

```text
sgd_logistic  standard  roc_auc 0.902  converged=true  median |score| 2.5e+00
sgd_logistic  robust    roc_auc 0.792  converged=true  median |score| 3.6e+01
sgd_logistic  none      roc_auc 0.605  converged=true  median |score| 2.6e+07
```

Unscaled SGD satisfies the optimiser's own criterion while its decision margins reach
twenty-six million. The mechanism the design originally relied on to detect procedural
failure does not fire for this failure at all.

This was caught in review **before** the freeze. ROC-AUC is therefore computed from the
estimator's own ranking score rather than a saturating probability: at those margins the
logistic link collapses every predicted probability onto {0, 1}, and ranking on probabilities
would have reported a tie-dominated number under a clean convergence flag in 64 of the 192
SGD factorial cells. `score_kind`, `n_unique_scores` and `score_abs_median` are recorded for
every fit so the pathology is data.

### Reproducibility is poor at the tightest tolerance

Split sensitivity, reference-conditioned, with 95% Wilson intervals:

| estimator | ε=0.001 | ε=0.005 | ε=0.010 |
|---|---|---|---|
| random_forest | 0.414 [0.26, 0.59] | 0.862 | 1.000 |
| linear_svm | 0.172 [0.08, 0.35] | 0.897 | 1.000 |
| sgd_logistic | 0.172 [0.08, 0.35] | 0.862 | 1.000 |
| logistic | 0.138 [0.06, 0.31] | 0.897 | 1.000 |

The tolerance you declare does more work than the method you describe.

---

## What makes this different from "we published our code"

Four mechanisms, each of which fails loudly rather than silently.

**Design lock.** Every file that determines the experiment — configuration, protocol, study
design, runtime policy, package lock and all source — is hashed. Any edit invalidates it.

**Preregistration capsule.** A deterministic document binding the design lock, the pinned
UCI source policy, the models, procedures, tolerances and exact per-family fit counts. It is
byte-reproducible: rebuilding it from the frozen design on a different operating system
yields identical bytes. Construction is refused once Adult source bytes or results exist.

**External anchor.** The capsule is retrieved back from its published location over
unauthenticated HTTPS and must match the local bytes exactly before Adult may be downloaded.
`load_adult()` never acquires data implicitly — loading and downloading are separate
operations, and acquisition is refused without a verified anchor.

**Release gate.** Fourteen checks, of which the last is the one that matters:
`full_empirical_replay` independently reconstructs **every** configured fit and requires it
to regenerate — metrics to the stored 12-significant-digit precision, and prediction hashes,
score hashes, score diagnostics and convergence outcomes exactly.

```text
edited raw CSV + edited manifest + edited derived tables  ⇒  still fails
```

unless the altered result can actually be produced by the locked experiment. The repository
carries regression tests that attempt exactly that coordinated tampering and confirm it is
rejected.

### The study reproduced itself

Executed twice in full, days apart, under two different anchors:

```text
 4 / 4   raw result families    byte-identical
11 / 11  derived analysis tables byte-identical
 4 / 4   run manifests          differ — they bind the anchor, as they must
```

---

## Reproducing it

The canonical environment is Python 3.13.5 with the exact package set in
`environment/requirements.lock.txt`, one estimator job and one numerical thread.

```bash
pip install -r environment/requirements.lock.txt
pip install --no-deps -e .

ml-repro --root . verify-design-lock     --config configs/adult.yml
ml-repro --root . verify-external-anchor  --config configs/adult.yml
ml-repro --root . download-data           --config configs/adult.yml
ml-repro --root . run-all                 --config configs/adult.yml
ml-repro --root . release-status          --config configs/adult.yml
```

Expect roughly 2.5 hours of CPU for the fits and the same again for each replay; the random
forest is almost all of it.

An offline profile using scikit-learn's bundled breast-cancer dataset exercises every model
and every procedure without touching Adult:

```bash
ml-repro --root . run-all        --config configs/smoke.yml
ml-repro --root . release-status --config configs/smoke.yml
```

Development checks: `ruff check .`, `mypy src`, `pytest` (38 tests).

## Layout

```text
configs/        adult.yml and the offline smoke profile
docs/           STUDY_DESIGN.md and the prospective PROTOCOL.md — both design-locked
src/            the experiment, the release gate and the anchoring machinery
artifacts/      design locks, the final experiment lock, the capsule, the anchor record
results/adult/  4 raw families, 11 derived tables, manifests, primary release manifest
environment/    runtime policy and the exact package lock
RELEASE_VALIDATION.md   execution record, results, deviations and limits
ROADMAP.md              what may change, and what may not
```

## Limits

**The gate passed on one platform.** Full replay requires bit-identical continuous-score
signatures, which depend on the BLAS build. A rerun on other hardware is expected to
reproduce every derived table while differing in score hashes. That is a platform
difference; it is not a failed reproduction and not evidence of tampering.

**Precision is bounded by 29 reruns.** Worst-case 95% interval half-width is 0.171. The
study does not claim to resolve moderate differences in reproduction rate between estimators
or between factors. Every rate is reported with its interval.

**Duplicate records are retained.** Adult contains 57 duplicate feature rows and 52 duplicate
labelled rows out of 48,842, matching conventional usage; the counts are recorded as dataset
provenance rather than silently removed.

**One scope claim, and no more.** This is one dataset and four estimators. It does not define
reproducibility for machine learning.

See [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md) for the full execution record, the
protocol deviation, and the complete results.

## Citation

See [CITATION.cff](CITATION.cff). Adult is Becker & Kohavi (1996), UCI Machine Learning
Repository, DOI `10.24432/C5XW20`.
