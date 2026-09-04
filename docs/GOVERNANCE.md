# ML dataset governance and lineage

This document describes the governance properties of the completed Adult reproducibility study without changing its frozen scientific specification.

The repository is not presented as a production model-governance platform. It is a completed machine-learning study with unusually strong controls over dataset identity, experiment identity, provenance, execution, and replay. The purpose of this document is to state exactly what is governed, how it is traced, and where the boundary lies.

## Governance questions answered by this repository

| Question | Evidence |
| --- | --- |
| Which exact source data was used? | `artifacts/adult_final_experiment_lock.json` pins the UCI Adult DOI, source URLs, and SHA-256 digests for `adult.data` and `adult.test`. |
| Can source-byte drift be detected? | Acquisition records and raw-data hashes are recorded in every Adult run manifest. A digest mismatch is a hard failure. |
| Which experimental specification produced the results? | `artifacts/adult_design_lock.json` hashes the config, protocol, study design, runtime policy, package lock, project metadata, and every source file under `src/ml_reproducibility/`. |
| Was the design fixed before primary data acquisition? | The preregistration capsule is externally anchored and data acquisition is refused until that anchor verifies. |
| Which split, estimator seed, preprocessing procedure, and model produced a fit? | Every raw result row records `experiment`, `model`, `split_seed`, `model_seed`, `preprocessing`, sample counts, metrics, convergence diagnostics, and behavioural signatures. |
| Which environment produced a result family? | Each run manifest records Python, package versions, platform, threadpool implementation, and execution policy, plus an environment digest. |
| Can outputs be linked to their inputs? | Each family manifest binds config hash, design-lock hash, dataset receipt, external anchor, environment, and output hashes. |
| Can the empirical result be reproduced rather than merely cross-checked? | The release gate independently reconstructs every configured fit and compares metrics, behavioural hashes, diagnostics, convergence outcomes, and derived tables. |

## Lineage chain

```text
UCI Adult DOI + canonical source URLs
        |
        v
source bytes: adult.data / adult.test
        |
        | SHA-256 + acquisition receipt
        v
frozen experiment specification
        |
        | design-lock SHA-256
        v
externally anchored preregistration capsule
        |
        | verified before acquisition
        v
training/test construction + preprocessing
        |
        | split_seed + preprocessing + model_seed
        v
individual model fit
        |
        | metrics + prediction_sha256 + score_sha256
        v
raw result family
        |
        | family manifest + output SHA-256
        v
derived analysis tables
        |
        | analysis manifest
        v
primary release manifest + independent empirical replay
```

The important property is that provenance is not inferred from filenames. The chain is represented by cryptographic digests and machine-readable manifests.

## Dataset identity and versioning

This study uses immutable content identity rather than a mutable semantic dataset version such as `v2` or `latest`.

For the primary dataset, the governed identity is the tuple

```text
(dataset DOI, source file name, source URL, SHA-256)
```

The final experiment lock records:

- UCI Adult DOI `10.24432/C5XW20`;
- the canonical `adult.data` and `adult.test` source URLs;
- SHA-256 digests for both source files;
- the rule that the two source files are concatenated before splitting;
- the target mapping;
- the duplicate-retention policy.

This is stronger than referring to a dataset only by name. If UCI were to serve different bytes under the same filename, the study would detect the change.

## Training and test dataset management

The study governs the split procedure through the frozen specification and records the `split_seed` used for every fit. Preprocessing is fitted inside the machine-learning pipeline, so transformations are learned from the training partition rather than from the complete dataset.

The repository deliberately does **not** claim to manage a separately persisted validation dataset. The primary design studies train/test splitting, estimator randomness, and preprocessing. Any interview or audit description should therefore say **training/test dataset management**, not invent a validation-set lifecycle that the study does not have.

## Experiment and model lineage

A fitted estimator is not stored in a production model registry. Instead, each fit is identified behaviourally and procedurally by the metadata required to reconstruct it:

```text
model class
hyperparameters
split seed
model seed
preprocessing procedure
source-data identity
environment
execution policy
prediction hash
continuous-score hash
metrics and diagnostics
```

This is experiment-level model lineage. It supports the question "what exact inputs and choices produced this result?" but it is not equivalent to a deployment registry with approval states, owners, production aliases, or endpoint history.

## Reproducibility

The repository distinguishes several levels that are often collapsed into one word:

1. **Specification reproducibility** — the design is deterministic and cryptographically locked.
2. **Data reproducibility** — the exact source bytes are identified and verified.
3. **Environment reproducibility** — the package set and runtime policy are fixed, while the observed numerical environment is recorded.
4. **Metric reproducibility** — repeated fits can be compared at declared tolerances.
5. **Behavioural reproducibility** — predictions and continuous scores are hashed, showing that the same metric does not imply the same model behaviour.
6. **Empirical replay** — the release gate reruns every configured fit rather than trusting internal consistency among stored files.

The study also records a real boundary: bit-identical continuous scores depend on the numerical platform. Cross-platform score-hash differences must not be silently treated as either success or tampering.

## Auditability and traceability controls

The governance controls fall into four layers.

### 1. Prospective controls

- frozen configuration and protocol;
- design lock over code and scientific inputs;
- preregistration capsule;
- immutable external anchor;
- refusal to acquire primary data before anchor verification.

### 2. Data controls

- canonical source URLs;
- source-byte SHA-256 digests;
- acquisition receipt;
- row and feature counts;
- duplicate counts and explicit duplicate policy.

### 3. Execution controls

- explicit split and model seeds;
- frozen estimator hyperparameters;
- frozen preprocessing procedures;
- package lock and runtime policy;
- machine, Python, package, threadpool, and execution metadata.

### 4. Result controls

- output-file hashes;
- prediction and score hashes per fit;
- family manifests;
- analysis manifest;
- primary release manifest;
- independent full empirical replay.

## What this repository does not claim

For governance discussions, these boundaries matter as much as the controls.

The repository does not provide:

- a production model registry or approval workflow;
- RBAC or enterprise access governance;
- PII classification or retention policy enforcement;
- a separately persisted validation-set registry;
- feature-store lineage across online and offline systems;
- deployed-model endpoint lineage;
- formal regulatory certification.

Those are legitimate enterprise-governance capabilities, but claiming them here would overstate the project.

## Interview summary

A concise description of the project is:

> I built a prospectively frozen classical-ML reproducibility study where the exact source dataset is content-addressed with SHA-256, the complete experimental specification is cryptographically locked, acquisition is gated by an externally anchored preregistration, each model fit records its split, seed, preprocessing, environment and behavioural signatures, and a release gate independently reconstructs every configured fit. That gives strong dataset provenance, experiment lineage, traceability and reproducibility, while stopping short of claiming a production model registry or enterprise access-governance system.
