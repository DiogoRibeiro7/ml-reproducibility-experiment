# Release validation — v0.5.0

## Scope

`v0.5.0` is a **pre-Adult empirical release**, like `v0.4.0` before it. It contains no Adult source bytes, no Adult acquisition receipt, no Adult model outputs and no primary empirical conclusion.

It exists because `v0.4.0` carried a defect in the reproducibility machinery itself.

## Why the design was re-frozen

`v0.4.0` wrote every scientific CSV and JSON artifact through Python text mode and `DataFrame.to_csv`, both of which emit the host platform's line ending. Identical science therefore produced different SHA-256 values on Windows and Linux.

The consequences were concrete and were reproduced before this release was prepared:

```text
v0.4.0 smoke release gate on Windows       10/12  FAIL
  derived_tables                           all 11 tables failed, on line endings alone
```

Separately, `v0.4.0` shipped no `.gitattributes`. Cloned with the Git-for-Windows default `core.autocrlf=true`, its artifacts hashed to:

```text
adult design lock    1f5fea91101fc7ce492d8d2a07f6ca22b964fda6fff976e1917bcf2cbe40d4c1
capsule              5cff8aeef4eb14266ceeae210946f342bb4c9c4405c721fbe0c62dff5bdcd533
```

instead of their frozen values, so `verify-design-lock` and `record-external-anchor` failed on a correct clone. The study could not be verified at all on a default Windows checkout.

Because the affected files (`release.py`, `experiment.py`, `provenance.py`, `design.py`, `data.py`, `anchor.py`, `cli.py`, `pyproject.toml`) are covered by the Adult design lock, correcting them necessarily invalidates the `v0.4.0` lock and capsule. That is why this is a scientific version change rather than an operational patch.

**The experimental design is unchanged.** Models, seeds, tolerances, preprocessing procedures, estimands and the 636-fit commitment are identical to `v0.4.0`.

## What changed

1. All scientific writes route through `src/ml_reproducibility/serialization.py`, which pins LF newlines and the 12-significant-digit float format. On Linux the emitted bytes are unchanged, so the correction is backwards-compatible with the canonical platform.
2. `.gitattributes` sets `* -text`, disabling Git end-of-line conversion.
3. `types-PyYAML` was added to the development dependencies and to CI. Without it `mypy src` fails on `config.py`, so the `v0.4.0` CI definition could not have passed its own type-check step.
4. `environment/runtime-policy.json` now declares the canonical platform and states which quantities are platform-portable.
5. `artifacts/release_manifest.json` moves to schema 5 and covers every tracked file. Schema 4 hashed 39 files and omitted `.github/workflows/ci.yml`, `LICENSE` and `.gitignore`, leaving the CI definition and the licence unprotected.

## Frozen identities

```text
Adult design lock SHA-256:
603e793cefa13a4a21bed9ecf70ef83aff90ee96d9c33fa503a8f1b08d92b355

Adult preregistration capsule SHA-256:
142d9de4824a2c80a100ace206812dc183ada6b5bc1a82ef52b3f76f112370a1

Smoke design lock SHA-256:
0ccef6d12cdb9f76a97abd93021e41fd74dbcde1dd1720ff0ade837874708758
```

The capsule reports `expected_raw_fit_count = 636`, with both pre-data assertions false, exactly as in `v0.4.0`.

## Canonical validation environment

Every result below was produced on the declared canonical platform:

```text
platform          Linux x86_64 (6.6.87.2-microsoft-standard-WSL2)
python            3.13.5
packages          exact match to environment/requirements.lock.txt (21/21)
BLAS              OpenBLAS 0.3.30 (Haswell)
n_jobs            1
numeric_threads   1
```

## Static analysis and tests — actually executed

`v0.4.0` honestly recorded that Ruff and mypy had never been run. They have now been run, at the versions the project pins, and the failures they found have been fixed.

```text
ruff 0.12.12      All checks passed          (v0.4.0: 6 errors)
mypy 1.17.1       Success, 14 source files   (v0.4.0: 32 errors, strict)
pytest            23 passed                  (v0.4.0: 17)
compileall        passed
```

`artifacts/release_manifest.json` now records `ruff_executed_locally: true` and `mypy_executed_locally: true`.

The six new tests are in `tests/test_serialization.py`. They pin the byte contract of every writer. Reintroducing the platform newline in either the CSV or the JSON path fails them:

```text
CRLF injected into the CSV writer   -> 2 tests fail
CRLF injected into the JSON writer  -> 3 tests fail
```

## Smoke release gate

```text
12/12 release checks passed
release_authorised = true
```

The checks are design lock, canonical reference environment, dataset provenance, the four raw families, environment consistency, baseline consistency, deterministic-control invariance, exact derived-table reconstruction, and full independent empirical replay.

## Continuity with v0.4.0

The re-freeze did not move the science. Comparing the regenerated smoke study against `v0.4.0`:

```text
10 of 11 derived tables   byte-identical
 1 of 11 derived tables   factorial_anova_roc_auc differs
```

The single difference is one F statistic:

```text
v0.4.0   sgd_logistic,C(model_seed),...,0.602666204968,...
v0.5.0   sgd_logistic,C(model_seed),...,0.602666204969,...
```

`sum_sq`, `df` and `share_total_ss` are identical to the last stored digit. The change is one unit in the twelfth significant figure, produced by a different OpenBLAS build, not by any change to the analysis.

## Cross-platform verification

The same release was independently checked on Windows against the canonical Linux artifacts:

```text
                                       v0.4.0        v0.5.0
derived tables reproduced byte-exact    0 / 11       10 / 11
smoke gate                             10 / 12       10 / 12
```

The line-ending defect is closed: 10 of 11 derived tables now reproduce byte-for-byte across operating systems, where previously none did.

Two checks still fail off the canonical platform, and both are expected:

```text
derived_tables          factorial_anova_roc_auc  (F statistic, 12th significant digit)
full_empirical_replay   split_sensitivity.score_sha256
```

Measured against the canonical Linux run, the Windows replay produced **identical predicted classes for every fit**, with metrics agreeing to `3.1e-13` — far inside the `1e-11` replay tolerance and the smallest declared reproducibility tolerance of `0.001`. Only the continuous-score SHA-256 signatures differ.

This is a property of the study, not a defect, and the gate is deliberately **not** relaxed to accommodate it. Behavioural score signatures are signatures of one numerical environment. A replication on other hardware that reproduces the derived tables while differing in score hashes has reproduced the conclusions and not the bytes, and `docs/PROTOCOL.md` requires that outcome to be reported as a platform difference rather than as a failed reproduction or as tampering.

## Negative pre-execution boundary test

With the v0.5.0 design lock and capsule in place and no external publication record:

```text
verify-external-anchor  exit status = 1
download-data           exit status = 1
```

Both fail at the external-anchor requirement. After the tests:

```text
adult.data    ABSENT
adult.test    ABSENT
receipt.json  ABSENT
data/raw/     not created
```

The boundary prevents acquisition through the supported CLI rather than merely documenting the intended order.

## Capsule determinism

The preregistration capsule was rebuilt from the frozen design on a second operating system and reproduced **byte-for-byte**. The capsule is a function of the locked design alone, not of the machine that generated it.

## Adversarial regression protection

The coordinated-tampering test remains active and passing: a non-reference raw result altered together with its behavioural hashes is still rejected by `full_empirical_replay`, because the gate reconstructs the fit independently.

## Adult release status

Deliberately unauthorised.

```text
design_lock            PASS
reference_environment  PASS
external_anchor        FAIL   no externally published capsule recorded
dataset                FAIL   unavailable without the anchor
raw_* (4 families)     FAIL   absent

release_authorised = false   (2/8)
```

This is the intended state.

## Next authorised action

External publication, not Adult execution.

The capsule must be published as an asset of an immutable release **in a public repository**. `record-external-anchor` retrieves the object with an unauthenticated HTTPS request; a private repository returns 404 to that request and cannot anchor the preregistration. Beyond the tooling, a preregistration only its author can read is not an external anchor.

Publish the exact bytes of `artifacts/adult_preregistration_capsule.json`, then run `record-external-anchor`. Only once the retrieved remote bytes match may Adult be acquired.
