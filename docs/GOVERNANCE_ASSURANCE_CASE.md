# Governance assurance case

This document summarises the governance argument that the repository can actually support from committed evidence.

It is deliberately narrower than a compliance assessment. It does not claim NIST AI RMF conformance, ISO/IEC 42001 certification, EU AI Act compliance, an independent audit opinion, or formal organizational risk acceptance.

## Argument structure

```text
claim
  -> implemented controls
  -> material residual risks
  -> concrete repository evidence
  -> explicit qualification / non-claim
```

## Supported claims

| Claim | Principal controls | Principal risks | Evidence examples | Qualification |
|---|---|---|---|---|
| Dataset identity and acquisition provenance are traceable | DATA-01, DATA-02 | RISK-01, RISK-06 | `governance/lineage_contract.json`, final experiment lock, external anchor | Scientific provenance only; no enterprise privacy/access/retention claim |
| Frozen scientific identity cannot be silently amended in place | DESIGN-01, DESIGN-02, CHANGE-01 | RISK-01, RISK-08 | design lock, preregistration capsule, change-control verifier, CI | Repository-level change control, not organizational approval governance |
| Train/test partition specification and usage are governed | PART-01 | RISK-03 | partition contract, partition tests | No prospectively persisted row-membership digest or separate validation registry |
| Each committed fit has deterministic executed-fit lineage | LINEAGE-01, RESULT-01 | RISK-04 | model-lineage contract, renderer, release manifest | Not a production model registry or deployment lineage system |
| Reference execution environment and numerical behaviour are auditable | EXEC-01, RESULT-01 | RISK-02 | runtime policy, lock file, manifests | BLAS/hardware score hashes may still diverge across platforms |
| Release authorisation uses independent reconstruction | ASSURE-01 | RISK-02, RISK-05 | release status, validation report, governance audit | Scientific assurance only; not external conformity assessment |
| Material residual risks are explicitly recorded | SCOPE-01, CHANGE-01 | RISK-01 through RISK-08 | risk register, control catalog | No invented owners, scores, appetite, or acceptance decisions |
| Framework mappings remain descriptive | SCOPE-01 | RISK-07 | control catalog, framework matrix, tests | No NIST/ISO/EU legal or certification claim |

## What this lets me say in an interview

A concise evidence-based formulation is:

> I built a prospectively frozen ML reproducibility study with content-addressed dataset identity, an externally anchored preregistration, deterministic train/test governance, per-fit lineage, environment capture, behavioural result hashes, independent release reconstruction, enforced change control, an evidence-backed control catalog, and an explicit residual-risk register. I also keep the boundaries explicit: it is not a production model registry, privacy-control system, formal risk-acceptance process, or compliance certification.

The important part is the final sentence. Governance credibility comes as much from knowing what the evidence does **not** support as from listing the controls that are present.

## Assurance boundary

The repository supports an assurance argument about scientific traceability, reproducibility, change integrity, and evidence discipline. It does not establish organizational accountability structures, production access control, privacy compliance, deployment security, regulatory conformity, or independent audit assurance.
