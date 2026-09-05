# Train/test partition governance

This document describes how the completed Adult study identifies and audits its train/test partitions without changing the frozen scientific specification.

## What is governed

The frozen study defines a repeated stratified hold-out using:

```text
sklearn.model_selection.train_test_split

test_size = 0.25
stratify = target
random_state = split_seed
```

The primary Adult data contains 48,842 rows after the canonical `adult.data` and `adult.test` files are concatenated. Every committed fit therefore records:

```text
n_train = 36,631
n_test  = 12,211
```

The study uses 30 declared split seeds, from 1729 through 1758. `governance/partition_contract.json` binds those partition specifications to the exact Adult source SHA-256 values and the frozen design-lock SHA-256.

## Partition specification identity

A partition specification receives a deterministic identifier:

```text
sha256(canonical JSON payload)
```

The payload includes:

- the two canonical Adult source-file SHA-256 values;
- the frozen design-lock SHA-256;
- the splitter implementation name;
- the test fraction;
- whether the split is stratified on the target;
- the split seed;
- total, training and test row counts.

For the baseline split seed `1729`, the governed identity is:

```text
sha256:c5e96bffb4fcbf1b2cd86a58b6d465a0cb1332a8bc42bfd1bed118382b057c61
```

This identifier means **the exact deterministic partition specification**, not a stored hash of the resulting row-membership vector.

## How committed fits use partitions

The four primary result families use split specifications as follows:

| Experiment | Governed split seeds | Fits |
| --- | --- | ---: |
| `split_sensitivity` | 1729–1758 | 120 |
| `seed_sensitivity` | 1729 | 120 |
| `preprocessing_sensitivity` | 1729 | 12 |
| `factorial` | 1729–1736 | 384 |
| **Total** | 30 distinct seeds | **636** |

`tests/test_partition_governance.py` reconstructs this usage from the committed result rows rather than trusting the table above.

## Important boundary: specification versus membership

The canonical Adult source bytes are deliberately excluded from Git. The completed study does not persist a train-row index hash and test-row index hash for each split.

Therefore this repository claims:

```text
source identity
+ frozen split algorithm
+ split seed
+ partition sizes
+ fit-to-seed traceability
= governed partition specification
```

It does **not** claim persisted row-membership lineage.

A future prospectively frozen study could add membership digests before execution, but adding them retrospectively to this completed study would blur the distinction between evidence captured during the experiment and evidence reconstructed later.

## Validation data

There is no separately governed validation partition in this study. The design uses train/test hold-out only. This is explicit in the machine-readable contract so interview or audit descriptions do not accidentally upgrade the project into a train/validation/test registry that it never implemented.
