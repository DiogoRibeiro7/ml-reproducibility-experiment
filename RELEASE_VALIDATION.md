# Release validation — primary Adult empirical release

## Status

This is no longer a pre-data release. The preregistered Adult experiment has been
executed, the release gate has authorised it, and the primary release manifest is
written.

```text
frozen design (tag)      v0.7.1  ->  30a0aec3e79c4ddd35c58e284185d702711b205a
adult design lock        2eb2351f4ae40971a5428c7aa6bbf3f906826ade0f99054abd56e03e3275d7d9
final experiment lock    a5729ae1263e9c3c853b99ee91eed21999cd368e455e60d5ef184b2bb1f2899c
preregistration capsule  8d791b1626d524822c0f72c7190353dcf5553cdee3918b57a81d89d33a06c0be
external anchor          public immutable release, publicly_retrievable = true
```

The design files are byte-identical at the freeze and after execution. `verify-design-lock`
passes against the post-run tree, so nothing scientifically relevant moved while the
results were being produced.

## Execution record

The study was executed twice: once under the withdrawn private anchor `v0.7.0`, and again
in full under the public anchor `v0.7.1` that is now in force. Only the second execution is
the release; the first is reported here because its results are what make the second
checkable.

```text
capsule published        immutable public release v0.7.1
anchor recorded          remote capsule == local capsule, retrieved anonymously
Adult acquired           both files match the pinned SHA-256 policy
run-all                  2026-08-29 21:05:04Z -> 2026-08-30 08:27:58Z
release gate             2026-08-30 08:27:58Z -> 11:18:12Z   14/14 PASS
finalise                 2026-08-30 11:18:12Z -> 14:14:30Z
```

Wall-clock times are inflated by host throttling; the fits consumed roughly 2 h 30 m of CPU
across an 11 h window. Throttling delays a replay, it cannot corrupt one.

### The re-execution reproduced the first run exactly

Comparing the two independent executions, days apart, under different anchors:

```text
4 / 4    raw result families    byte-identical
11 / 11  derived tables         byte-identical
4 / 4    run manifests          differ — they bind the new anchor, as they must
```

All 636 fits regenerated bit-for-bit. The only changes are in the provenance records that
are supposed to change. This is the study's own reproducibility claim, tested on itself.

## Release gate

```text
14/14 checks passed, release_authorised = true
```

design_lock · reference_environment · external_anchor · dataset · the four raw families ·
environment_consistency · analysis_manifest · baseline_consistency · deterministic_controls ·
derived_tables · full_empirical_replay

`full_empirical_replay` reconstructed every one of the 636 configured fits from the locked
design and required them to regenerate: metrics at the stored 12-significant-digit
precision, and prediction hashes, score hashes, score diagnostics and convergence outcomes
exactly.

An independent structural check (`check_primary_outputs.py`, which does not use the
experiment's own verification code) passed 21/21 against the completed outputs.

## Primary results

### Reproducing a metric does not reproduce the model

Across 29 genuine estimator-seed reruns with the test set held fixed:

| model | ROC-AUC reproduced at ε=0.001 | distinct prediction vectors | exact prediction match |
|---|---|---|---|
| random_forest | 29/29 | 30 / 30 | **0.000** |
| sgd_logistic | 27/29 | 30 / 30 | **0.000** |
| logistic | 29/29 | 1 | 1.000 (deterministic) |
| linear_svm | 29/29 | 1 | 1.000 (deterministic) |

Thirty runs of the random forest agree on ROC-AUC to within 0.001 and not one of them
makes the same predictions as the reference. Agreement on the reported number is fully
compatible with disagreement about which observations receive which label.

### Variance attribution separates by estimator

Share of ROC-AUC sum of squares in the 8 × 8 × 3 crossed design:

| | split_seed | model_seed | preprocessing |
|---|---|---|---|
| random_forest | **98.9%** | 0.1% | 0.0% |
| sgd_logistic | 0.5% | 0.8% | **87.2%** |

Conditioning either conclusion on a single arbitrary baseline would have been misleading.
This is what the crossed design exists to prevent.

### Reference-conditioned and pairwise reproducibility

Split sensitivity, ROC-AUC, with 95% intervals:

| model | ε=0.001 reference | ε=0.001 pairwise | ε=0.010 reference | ε=0.010 pairwise |
|---|---|---|---|---|
| random_forest | 0.414 [0.255, 0.593] | 0.280 [0.173, 0.388] | 1.000 [0.883, 1.000] | 0.991 [0.973, 1.000] |
| logistic | 0.138 [0.055, 0.306] | 0.202 [0.125, 0.280] | 1.000 [0.883, 1.000] | 0.986 [0.962, 1.000] |
| linear_svm | 0.172 [0.076, 0.345] | 0.195 [0.119, 0.272] | 1.000 [0.883, 1.000] | 0.989 [0.967, 1.000] |
| sgd_logistic | 0.172 [0.076, 0.345] | 0.177 [0.106, 0.248] | 1.000 [0.883, 1.000] | 0.982 [0.952, 1.000] |

Reproducibility at the tightest declared tolerance is poor for every model. The declared
precision limit of the 29-rerun design (worst-case 95% half-width 0.171) applies to all of
these, and the two estimands are not interchangeable: the reference-conditioned rate
describes reproducing one published number, the pairwise rate describes two independent
legitimate executions agreeing with each other.

### Procedure sensitivity

Maximum absolute ROC-AUC drift from the reference procedure:

```text
logistic        0.000006      random_forest   0.000029
linear_svm      0.332812      sgd_logistic    0.296857
```

Procedure-stability fractions at ε=0.010 are 1.0 for logistic and random forest, 0.5 for
the linear SVM and **0.0** for SGD: neither alternative procedure lands within tolerance.

### Convergence reports perfect health, and is wrong

```text
636 / 636 fits converged        total convergence warnings: 0
```

Every fit in the study, under every procedure, reports successful convergence. Yet:

```text
sgd_logistic  standard  roc_auc 0.902  median |score| 2.5e+00
sgd_logistic  robust    roc_auc 0.792  median |score| 3.6e+01
sgd_logistic  none      roc_auc 0.605  median |score| 2.6e+07
```

Unscaled SGD converges by the optimiser's own criterion while its margins reach 26 million.
The convergence diagnostic — the mechanism the design originally relied on to detect
procedural failure — does not fire for this failure at all.

This was found during pre-freeze review on synthetic data at Adult's numeric scale, and it
is why ROC-AUC is computed from the estimator's own ranking score rather than from a
saturating probability. Ranking on probabilities would have collapsed this cell onto a
handful of tied values and reported a meaningless metric under a clean convergence flag,
in 64 of the 192 SGD factorial cells. `score_abs_median` and `n_unique_scores` are recorded
for every fit so the pathology is observed data rather than a silent artifact.

## Deviation from the frozen protocol

`docs/PROTOCOL.md` is covered by the design lock. Its "Anchor visibility" section states
that the capsule is published to an immutable release **in a private repository** with
`kind = github_private_release_asset`, and spells out that such an anchor cannot prove
prospectivity to an independent reader.

That is not what happened. The study was anchored twice:

```text
v0.7.0  private immutable release, github_private_release_asset   WITHDRAWN
v0.7.1  public  immutable release, github_release_asset           IN FORCE
```

The private release `v0.7.0` was withdrawn when the repository history was rewritten to
remove a personal email address from commit metadata. Because GitHub permanently reserves a
tag name once an immutable release has used it, `v0.7.0` could not be recreated, and the
study was re-anchored on `v0.7.1` in a public repository. The design content is unchanged
across both: the frozen tree hash is identical, and so are the design lock, the final
experiment lock and the capsule.

**The frozen protocol has deliberately not been edited to match.** Rewriting a preregistered
document so that it agrees with what was actually done is the specific failure mode
preregistration exists to prevent, and the fact that this particular deviation *strengthens*
the evidence is not a reason to make an exception. The protocol stands as written; this is
the deviation record.

The deviation moves the anchor from author-verifiable to publicly verifiable. Every
constraint the protocol imposes on execution order was still met: the capsule was built
before any Adult byte was retrieved, the anchor was verified before acquisition, and the
636 fits were executed under the anchor their manifests bind.

## Limits on what may be claimed

**The anchor is public and independently checkable.** The capsule is an asset of the
immutable public release `v0.7.1`. Anyone can retrieve it without credentials and confirm
it matches the design the results claim to follow:

```bash
curl -fsSL https://github.com/DiogoRibeiro7/ml-reproducibility-experiment/releases/download/v0.7.1/adult_preregistration_capsule.json | sha256sum
# 8d791b1626d524822c0f72c7190353dcf5553cdee3918b57a81d89d33a06c0be
```

The anchor record carries `publicly_retrievable: true`, and the capsule embeds the complete
final experiment lock, so it can be read as a specification rather than only hashed.

**The gate passed on one platform.** `full_empirical_replay` requires bit-identical
continuous-score signatures, which depend on the BLAS build. Verification on other hardware
is expected to reproduce every derived table while differing in score signatures. That is a
platform difference and must be reported as one, not as a failed reproduction.

**Precision is limited by design.** 29 genuine reruns give a worst-case 95% interval
half-width of 0.171. The study does not claim to resolve moderate differences in
reproduction rate between models or between factors. Every reported rate carries its
interval.

**Duplicate records are retained.** Adult contains 57 duplicate feature rows and 52
duplicate labelled rows out of 48,842, matching conventional usage. The counts are recorded
as dataset provenance. At 0.1% the resulting optimism shifts metric levels slightly and is
not a plausible driver of the between-run variation the study measures.
