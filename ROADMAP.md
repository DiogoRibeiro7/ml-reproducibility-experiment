# Roadmap

This repository contains a **completed, prospectively frozen study**. The scientific result is
not an evolving product feature: the Adult experiment has already been specified, externally
anchored, executed, independently reconstructed, and released. Work on the current release
therefore has to do one of two things without changing the frozen experiment:

1. strengthen the evidence around the completed release; or
2. document limitations and prepare a genuinely new prospective study.

Routine-looking changes to the frozen scientific specification are neither of those things.
They create a new experimental identity and must be treated as such.

## Current state

The repository now has two deliberately separate layers:

```text
frozen scientific release
        ↓
governance and assurance evidence around that release
```

The scientific layer remains the prospectively frozen Adult study. The governance layer is
additive: it explains, tests, and audits what can be established from the completed evidence
without retrospectively changing what was preregistered or executed.

### Completed scientific release

The current Adult release is complete:

- the study design was frozen before primary-data retrieval;
- the preregistration capsule was externally anchored at immutable release `v0.7.1`;
- UCI Adult source files are content-addressed by SHA-256 and DOI;
- 636 primary fits were executed under the frozen design;
- the release gate independently reconstructed every configured fit;
- release validation passed all 14 release checks;
- published metrics and behavioural signatures are retained as immutable evidence.

There is no planned amendment to this scientific release.

### Completed governance evidence programme

The repository now also has a coherent governance chain around the completed study:

```text
dataset provenance
    ↓
train/test partition governance
    ↓
executed-fit model lineage
    ↓
immutable change control
    ↓
control catalog
    ↓
risk register
    ↓
assurance case
```

Implemented governance artifacts include:

- `docs/GOVERNANCE.md` and `governance/lineage_contract.json` for dataset, run, and result
  provenance;
- `governance/audit_report.md` for generated release-evidence verification;
- `governance/partition_contract.json` and `docs/PARTITION_GOVERNANCE.md` for deterministic
  train/test partition-specification identity and usage;
- `governance/model_lineage_contract.json` and `docs/MODEL_LINEAGE.md` for deterministic
  executed-fit lineage across all 636 fits;
- `governance/change_control_policy.json` and `docs/CHANGE_CONTROL.md` for protecting the
  completed scientific identity against in-place redefinition;
- `scripts/verify_change_control.py`, enforced in CI, which checks the frozen scientific tree
  against the externally immutable `v0.7.1` preregistration release rather than trusting
  mutable local hashes;
- `governance/control_catalog.json` and `docs/GOVERNANCE_CONTROL_MATRIX.md` for an
  evidence-backed control catalog and descriptive framework crosswalk;
- `governance/risk_register.json` and `docs/GOVERNANCE_RISK_REGISTER.md` for evidenced risks,
  mitigations, and residual boundaries without inventing organizational risk acceptance;
- `governance/assurance_case.json` and `docs/GOVERNANCE_ASSURANCE_CASE.md` for the final
  claim → control → risk → evidence → qualification argument.

These artifacts demonstrate strong dataset provenance, traceability, reproducibility,
executed-fit lineage, release assurance, change control, and evidence-backed risk reasoning.
They do **not** turn this research repository into an enterprise AI governance system.

---

## The constraint that shapes every next step

Two identities live in this repository and they move independently:

```text
software identity      the version of repository code and governance material
experimental identity  the frozen scientific specification
```

A change to the software or governance overlay does not redefine the experiment. A change to
the **experiment** requires a new prospective freeze — a new design lock, a new capsule, a
new external anchor, fresh primary-data acquisition, fresh execution, and a new release
decision. Results from the completed release cannot simply be relabelled as results of the new
specification.

### Frozen scientific files

The authoritative set is the file map in `artifacts/adult_design_lock.json`. It includes:

```text
configs/adult.yml
docs/PROTOCOL.md
docs/STUDY_DESIGN.md
environment/runtime-policy.json
environment/requirements.lock.txt
pyproject.toml
src/ml_reproducibility/*.py
```

There is no such thing as a small tooling fix to `src/` for this completed study. The release
gate itself is part of the preregistered scientific specification.

CI now verifies this boundary against the externally immutable `v0.7.1` preregistration
capsule before smoke execution.

### Additive work that may continue

Documentation, governance artifacts, tests, CI, figures, and release commentary may continue
to improve provided they do not rewrite the completed scientific identity or historical
evidence.

Strengthening tests is explicitly allowed. Retrospectively changing frozen scientific files
is not.

---

## Next priorities on the current release

Only work that adds genuinely new evidence is still worth doing on this release. More
parallel governance documents without new evidence are not a priority.

### 1. Add a second independently controlled immutable anchor

This is the highest-value remaining item.

The preregistration capsule is currently anchored to one immutable GitHub release. That is
stronger than a mutable repository reference, but it is still one hosting platform and one
institutional trust path. The existing implementation already supports `kind =
doi_archive_file`, so the same capsule bytes can be deposited in a DOI-backed archive under
independent control.

Success means:

- the exact existing preregistration capsule bytes are deposited unchanged;
- the archive exposes an immutable DOI-backed reference;
- the archived SHA-256 equals the existing capsule SHA-256;
- the second anchor is recorded additively without rewriting the original release evidence.

No scientific code change is required.

### 2. Document the cross-platform reproducibility boundary with real evidence

`full_empirical_replay` deliberately requires bit-identical continuous-score signatures.
Those signatures can differ across BLAS builds or hardware even when higher-level derived
results agree.

The next useful contribution is not to weaken the gate. It is to produce a worked independent
replication showing the exact divergence pattern, for example:

```text
derived tables        identical
metric values         equivalent or identical
prediction hashes     potentially identical
continuous-score hash different
platform / BLAS       different
```

That would turn the current platform caveat into auditable evidence rather than expert-only
interpretation.

### 3. Independent replication on another environment

A truly independent run remains more valuable than additional repository scaffolding.

The replication should record:

- platform, Python, package, BLAS, and threadpool details;
- whether all derived tables reproduce;
- which behavioural signatures reproduce exactly;
- which score signatures differ;
- whether the observed differences fit the documented platform boundary.

The result should be added as replication evidence, not used to rewrite the original release.

---

## Governance work that is deliberately not being claimed

The completed governance programme is evidence-backed, but its scope is narrow and explicit.
This repository does not demonstrate or certify:

- enterprise RBAC or segregation of duties;
- consent, privacy-law, retention, or deletion enforcement;
- production model-registry approval and promotion workflows;
- persisted trained-model binaries or deployment endpoint lineage;
- a separately governed validation-set registry;
- prospectively persisted row-membership hashes;
- organizational risk ownership, risk appetite, or formal risk acceptance;
- NIST AI RMF conformance;
- ISO/IEC 42001 certification;
- EU AI Act compliance or high-risk-system classification;
- an independent audit or conformity-assessment opinion.

If those capabilities are required, they must be evidenced in the organizational data and
production MLOps environment. They should not be manufactured inside this completed research
repository simply to make the governance story look broader.

---

## Requires a new prospective freeze

The items below are new studies, not amendments to the completed Adult release.

### Multi-dataset external validity

The strongest scientific limitation remains one dataset and four estimators. A successor
should test whether the observed split, seed, and preprocessing sensitivity patterns hold
across multiple datasets and problem settings.

### Platform as a designed experimental factor

The current study treats cross-platform numerical divergence as a reproducibility boundary.
A successor could prospectively make platform or BLAS implementation an experimental factor
and estimate the distribution of resulting score-signature divergence.

### Tighter reproduction-rate precision

With 29 genuine reruns, the worst-case 95% interval half-width is about **0.171**. Reaching
approximately ±0.05 requires far more reruns. A successor should budget for that prospectively
or narrow the estimand.

### Observation-level instability

The current behavioural result records whether prediction vectors match. It does not identify
which observations repeatedly change label across reruns. A successor could prospectively
study observation-level instability and whether the same records repeatedly sit near decision
boundaries.

### Probability calibration reproducibility

The current headline analysis focuses on ranking metrics and estimator-native scores.
Reproducibility of calibrated probabilities is a distinct question and should be treated as a
new estimand in a new frozen study.

### Prospective row-membership and validation governance

If future work requires stronger dataset-governance evidence, a successor should persist
train/test membership digests prospectively and define any validation partition before data
access. Those identities must not be retrofitted onto the completed study.

---

## Explicitly out of scope

**Changing the frozen study to improve its results.** If a genuine defect is found, document
it, state which claims it affects, and create a new prospective specification where necessary.
Do not edit the completed design to make the evidence look cleaner.

**Weakening the release gate.** In particular, do not relax `full_empirical_replay` merely so
a cross-platform run passes. A successor may classify divergence more finely; the completed
release must keep detecting it.

**Editing `docs/PROTOCOL.md` to match what happened.** The anchor deviation is already
recorded in `RELEASE_VALIDATION.md`. Rewriting a preregistered document after execution would
defeat the point of preregistration.

**Retrofitting missing governance evidence.** Row-membership hashes, validation identities,
organizational approvals, and production deployment lineage that were not prospectively
recorded must remain absent claims.

**Deep learning.** Out of scope by design. This study concerns the conventional classical-ML
workflow.

---

## Invariants for any successor study

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
9. New dataset, partition, model, environment, or analysis identities are defined
   prospectively rather than backfilled from completed outcomes.
10. Governance claims remain proportional to evidence: descriptive framework mappings are
    never presented as compliance, certification, audit, or organizational approval.
