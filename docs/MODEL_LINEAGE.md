# Executed-fit model lineage

This document describes how the completed Adult study can assign stable lineage identities to every executed model fit without pretending that the repository contains a production model registry.

## What is governed

Each of the 636 committed fit rows is linked through six deterministic identities:

```text
partition_spec_id
        |
        v
preprocessing_spec_id + model_spec_id
        |
        v
training_spec_id
        |
        v
execution_spec_id
        |
        v
fit_evidence_id
```

The identities are derived from evidence already committed by the frozen study.

### Partition specification

`partition_spec_id` binds the exact Adult source SHA-256 values, frozen design-lock digest, train/test splitter, test fraction, stratification rule, split seed, and observed train/test sizes.

It is a partition **specification** identity. The repository does not claim persisted row-membership hashes.

### Preprocessing specification

`preprocessing_spec_id` binds the frozen preprocessing variant and its exact transformer definition from `artifacts/adult_final_experiment_lock.json`.

### Model specification

`model_spec_id` binds the estimator class and effective hyperparameters. For stochastic estimators, the placeholder random state in the frozen lock is replaced by the declared `model_seed` used by that fit.

### Training specification

`training_spec_id` combines dataset/design identity, partition specification, preprocessing specification, model specification, and model seed. It answers:

> What exact governed training procedure defines this fit?

### Execution specification

`execution_spec_id` adds the experiment family, configuration digest, observed environment digest, and execution policy. The same training specification can therefore remain distinguishable when executed in different experiment families.

### Fit evidence

`fit_evidence_id` binds the execution specification to the complete committed result row and the corresponding family manifest. The result row includes metrics, convergence diagnostics, prediction SHA-256, and continuous-score SHA-256.

This gives an auditable chain from source data and design through model procedure to observed behaviour.

## What is not governed

The study does **not** persist trained estimator binaries. Therefore these records are not equivalent to:

- a production model registry;
- model approval or promotion states;
- deployment endpoint history;
- inference-service version lineage.

Those would require different production artefacts and controls.

## Why this matters

A model metric alone is not enough to identify what happened. In this study, two fits can report nearly identical ROC-AUC while producing different prediction vectors. The lineage identifiers make the full procedural and behavioural context explicit rather than treating the metric as the model's identity.

## Generate the lineage records

```bash
python scripts/render_model_lineage.py
```

This writes one JSON object per committed fit to `governance/model_lineage.jsonl`. The file is a derived audit surface; the authoritative evidence remains the frozen experiment lock, governance contracts, raw result tables, and family manifests.
