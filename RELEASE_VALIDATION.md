# Release validation — v0.4.0

## Scope

`v0.4.0` is a **pre-Adult empirical release**. Its purpose is to make the prospective publication boundary machine-verifiable before the primary UCI Adult experiment is executed.

The release does **not** contain Adult source bytes, an Adult acquisition receipt, Adult model outputs, or a primary empirical conclusion.

## Prospective primary design

The locked Adult study contains

\[
120_{\text{split}}
+
120_{\text{seed}}
+
12_{\text{procedure}}
+
192_{\text{SGD factorial}}
+
192_{\text{RF factorial}}
=
\boxed{636\text{ fits}}.
\]

Final Adult design-lock SHA-256:

```text
c2062027931090934e8a6bf32b38c319e34f9a1ba0b17fba0a6f492f48aa57a1
```

The lock verifies after the final source and protocol changes.

## Deterministic preregistration capsule

The final pre-data capsule is:

```text
artifacts/adult_preregistration_capsule.json
```

SHA-256:

```text
c610b3c867a6322d64dafce5f22f5568d6e397c23031a121ec9ef72b57d6609b
```

The capsule reports:

```text
expected_raw_fit_count = 636
adult_source_bytes_present_when_capsule_built = false
adult_empirical_outputs_present_when_capsule_built = false
```

Its content includes the complete design-lock payload, configuration digest, pinned UCI source policy, model and preprocessing sets, primary metric, reproducibility tolerances and exact family fit counts.

Capsule construction is explicitly rejected if canonical Adult source bytes or Adult empirical outputs are already present.

## Remote-anchor hardening

`v0.3.0` required a local anchor record but did not independently retrieve the claimed external object. `v0.4.0` closes that gap.

`record-external-anchor` now:

1. verifies the local design lock and preregistration capsule;
2. requires an HTTPS external object;
3. retrieves the remote object;
4. requires the remote bytes to equal the local capsule **exactly**;
5. checks that the remote JSON binds the same design lock and configuration;
6. records local, remote and design-lock hashes only after those checks pass.

For `github_release_asset`, the URL must have the form

```text
https://github.com/<owner>/<repo>/releases/download/<ref>/<asset>
```

and `<ref>` must equal `immutable_ref`.

An established `adult_external_anchor.json` is not silently overwritten.

## Anchor binding after acquisition

Adult acquisition now writes a schema-2 receipt that binds:

- the UCI Adult DOI;
- canonical Adult source hashes;
- the retrieval timestamp recorded by the execution environment;
- the verified local external-anchor hash;
- the local preregistration-capsule hash;
- the independently retrieved remote-capsule hash;
- the immutable external reference and URL.

Adult loading verifies that receipt when an empirical run is requested. Every Adult raw-run manifest and the analysis manifest bind the same anchor evidence. The final primary release manifest also records the anchor identity.

Consequently, replacing the external-anchor record after empirical execution invalidates both the data provenance and result-manifest chain.

## Negative pre-execution boundary test

With the final v0.4.0 design lock and capsule in place, but no external publication record:

```text
verify-external-anchor exit status = 1
download-data          exit status = 1
```

Both fail at the external-anchor requirement, before Adult acquisition.

After those tests:

```text
adult.data   ABSENT
adult.test   ABSENT
receipt.json ABSENT
```

Therefore the boundary does not merely document the intended order; it prevents primary data acquisition through the supported CLI before the remote capsule is established.

## Smoke release gate

The offline scikit-learn breast-cancer profile was rebuilt under the final v0.4.0 source tree and smoke design lock.

Result:

\[
\boxed{12/12\text{ release checks passed}}.
\]

The checks are:

1. design lock;
2. canonical reference environment;
3. dataset provenance;
4. split-sensitivity raw family;
5. seed-sensitivity raw family;
6. preprocessing-sensitivity raw family;
7. factorial raw family;
8. environment consistency;
9. baseline consistency;
10. deterministic-control invariance;
11. exact derived-table reconstruction;
12. full independent empirical replay.

The smoke release status is `release_authorised = true`.

## Repeatability check

The complete smoke experiment was executed twice consecutively under the same final v0.4.0 environment.

All 20 scientific CSV/manifest files were SHA-256 identical between executions.

The canonical hashes are stored in:

```text
artifacts/smoke_scientific_hashes.sha256
```

This includes the raw experiment families, their manifests, all derived tables and the analysis manifest.

## Adversarial regression protection

The existing coordinated-tampering test remains active: a non-reference raw result can be altered together with its behavioural hashes, but `full_empirical_replay` reconstructs the model fit independently and rejects the modified result.

The new anchor test suite adds the following protections:

- a capsule must represent the complete 636-fit locked Adult design;
- capsule creation fails after an Adult source file appears;
- a remote object differing by even one byte from the local capsule is rejected;
- non-HTTPS anchor URLs are rejected;
- a GitHub release asset whose URL tag disagrees with `immutable_ref` is rejected.

## Unit and syntax validation

Final local test result:

\[
\boxed{17/17\text{ tests passed}}.
\]

`python -m compileall src tests` also passes.

Ruff and mypy are configured in `pyproject.toml` and CI. They were not available in the isolated validation runtime, and network access was unavailable for installing them, so they are **not** falsely reported as locally executed.

A manual line-length check found no Python source or test line exceeding the configured 100-character Ruff limit.

## Adult release status

The current Adult release status is deliberately unauthorised.

The passing pre-execution gates are:

```text
design_lock            PASS
reference_environment  PASS
```

The external-anchor gate fails because no externally published capsule has yet been recorded. Dataset and empirical-result gates therefore also remain unavailable or missing.

This is the intended state for v0.4.0.

## Next authorised action

The next legitimate action is **external publication**, not Adult execution.

Publish the exact bytes of:

```text
artifacts/adult_preregistration_capsule.json
```

through a stable HTTPS release/archive object, then run `record-external-anchor`. Only after the retrieved remote bytes match the capsule may the primary Adult source files be acquired.
