# Roadmap

This repository holds a **completed, prospectively frozen study**. That makes its roadmap
unusual: most of what a normal project would treat as routine improvement is, here, either
forbidden or expensive. This document says which is which before anyone opens a pull request.

## The constraint that shapes everything

Two identities live in this repository and they move independently:

```text
software identity      the version of the code
experimental identity  the frozen scientific specification
```

A change to the software does not redefine the experiment. A change to the **experiment**
requires a new prospective freeze — a new design lock, a new capsule, a new external anchor,
and a fresh execution. The results already published cannot be reused under a new
specification, because every manifest binds the anchor it was produced under.

### What is locked

The design lock covers these, and editing any of them invalidates the freeze:

```text
configs/adult.yml
docs/PROTOCOL.md
docs/STUDY_DESIGN.md
environment/runtime-policy.json
environment/requirements.lock.txt
pyproject.toml
src/ml_reproducibility/*.py        ← all of it, including the release gate
```

Note the last line. **There is no such thing as a small tooling fix to `src/`.** A bug fix
in the release gate is a scientific change to this study, because the gate is part of what
the preregistration committed to.

### What is not locked

```text
README.md   RELEASE_VALIDATION.md   ROADMAP.md   CITATION.cff   LICENSE
Makefile    .github/workflows/      tests/       figures/
```

Tests are deliberately outside the lock: strengthening the evidence that the locked code
behaves as specified does not change what was specified. New regression tests are welcome
against this release.

---

## Open on this release

Work that can proceed without touching the frozen specification.

### A second, independent anchor

The capsule is currently anchored to one immutable GitHub release. `anchor.py` already
supports `kind = doi_archive_file`, so publishing the same capsule bytes to a DOI-backed
archive would add an anchor under different institutional control, with independent
timestamping. No code change; the anchor record is additive.

This is the highest-value open item. A single-host anchor is a single point of trust.

### Documentation of the platform boundary

`full_empirical_replay` requires bit-identical continuous-score signatures, which depend on
the BLAS build. Today a replication on other hardware fails the gate, and the failure looks
identical to tampering until a human reads the diff. Worked examples showing what a genuine
platform difference looks like — derived tables identical, score hashes differing — would
make that distinction checkable by a reader rather than by an expert.

### Independent replication

The most useful contribution anyone can make to this release is to run it somewhere else and
report what happened. Expect all eleven derived tables to reproduce byte-for-byte and the
score signatures to differ.

---

## Requires a new prospective freeze

Each of these is a **new study**, not an amendment. Listing them here is a design note, not
a commitment.

### Beyond one dataset

The strongest limitation of this release is stated plainly in its own README: one dataset,
four estimators. Whether the split-versus-preprocessing split of variance is a property of
Adult, of tabular data generally, or of these estimators, is unanswered. A multi-dataset
design is the obvious successor and would need its own freeze.

### Platform as a designed factor

This study treats cross-platform divergence as a limitation. A successor could treat it as
an experimental factor: run the same locked design across several BLAS builds and report the
distribution of score-signature divergence directly. That converts a caveat into a result.

### Tighter precision

29 genuine reruns give a worst-case 95% interval half-width of **0.171** — wide enough that
a reproduction rate of 0.35 and one of 0.65 are not distinguishable. Reaching ±0.05 needs
roughly 384 reruns per family, which is dominated by random-forest cost. A successor should
either budget for it or narrow the estimand.

### Which observations flip

The behavioural result here is binary: prediction vectors match or they do not. It does not
say *which* observations change label between runs, or whether the same individuals are
repeatedly unstable. For any application where the labels attach to people, that is the
question that matters.

### Calibration, not just ranking

ROC-AUC is a rank statistic, and this study deliberately ranks on the estimator's own score.
Whether *calibrated probabilities* reproduce is a separate question, and the unscaled-SGD
result suggests the answer may be considerably worse.

---

## Explicitly out of scope

**Changing the frozen study to improve its results.** The design is fixed. If a genuine
defect is found, the correct response is to document it, invalidate the affected claims, and
freeze a new specification — not to edit this one.

**Weakening the release gate.** In particular, relaxing `full_empirical_replay` so that a
platform difference passes. The gate's strictness is the reason its verdict means anything.
A successor may *classify* divergence more finely; it may not stop detecting it.

**Editing `docs/PROTOCOL.md` to match what happened.** The protocol currently describes a
private anchor that was later replaced with a public one. That divergence is recorded in
`RELEASE_VALIDATION.md` as a deviation. Rewriting a preregistered document so it agrees with
the execution is the specific failure preregistration exists to prevent, and the fact that
this particular deviation strengthened the evidence is not a reason to make an exception.

**Deep learning.** Out of scope by design, not by oversight. The subject is the conventional
classical-ML workflow.

---

## Invariants

Whatever changes, these hold across any successor study:

1. The design is frozen and externally anchored **before** any primary data byte is retrieved.
2. Loading and downloading remain separate operations; acquisition is refused without a
   verified anchor.
3. The release gate independently reconstructs every configured fit. Consistency between
   stored artifacts is never sufficient.
4. The reference observation is never counted as a reproduction of itself.
5. Deliberately selected procedures are reported as a stability fraction, never as a
   probability.
6. Non-convergent and pathological fits are reported, never silently excluded.
7. Every reported rate carries an interval, and the interval respects the dependence
   structure of its estimand.
8. Deviations are recorded. Frozen documents are not edited to match reality.
