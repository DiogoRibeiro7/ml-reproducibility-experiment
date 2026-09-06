# Governance control matrix

This matrix translates the repository's existing technical evidence into a compact AI/ML governance control view. It is an **evidence crosswalk**, not a compliance statement, certification, legal opinion, or claim that this study is a regulated high-risk AI system.

The framework references are intentionally broad. NIST AI RMF 1.0 is mapped at function level. ISO/IEC 42001:2023 is mapped at publicly described management-system themes, not paid clause text. EU AI Act references point only to relevant high-risk-system governance themes such as data governance, technical documentation, and record-keeping.

| Control | Objective | Evidence | Framework themes | Boundary |
|---|---|---|---|---|
| DATA-01 | Immutable source-data identity | `governance/lineage_contract.json`, final lock | NIST GOVERN/MAP; ISO traceability/data governance; EU AI Act Arts. 10–11 | No fairness, privacy, or legal-basis certification |
| DATA-02 | Acquisition provenance before primary-data retrieval | external anchor, preregistration capsule | NIST GOVERN/MAP; ISO accountability/traceability; EU Arts. 10–11 | No enterprise access/retention/consent governance |
| PART-01 | Govern train/test split specification and usage | partition contract + regression tests | NIST MAP/MEASURE; ISO data quality/traceability; EU Arts. 10–11 | No validation registry or persisted membership digest |
| DESIGN-01 | Freeze scientific specification | design lock + preregistration | NIST GOVERN/MAP/MANAGE; ISO policy/risk/change themes; EU Art. 11 | Not an enterprise approval workflow |
| DESIGN-02 | External immutable preregistration anchor | `v0.7.1` anchor | NIST GOVERN/MANAGE; ISO accountability/traceability; EU Arts. 11–12 | Still one external hosting trust dependency |
| EXEC-01 | Constrain and record execution environment | runtime policy, lockfile, manifests | NIST MEASURE/MANAGE; ISO reliability/monitoring; EU Art. 11 + Annex IV | Cross-platform score hashes remain BLAS-sensitive |
| LINEAGE-01 | Deterministic executed-fit lineage | model-lineage contract + renderer | NIST GOVERN/MEASURE/MANAGE; ISO traceability/transparency; EU Arts. 11–12 | No stored model binaries or deployment lineage |
| RESULT-01 | Bind fit outputs to metrics and behavioural signatures | release/model lineage evidence | NIST MEASURE/MANAGE; ISO monitoring/reliability; EU Arts. 11–12 | Not production telemetry |
| ASSURE-01 | Independently reconstruct every configured fit | release gate + audit report | NIST MEASURE/MANAGE; ISO assurance/monitoring; EU Art. 11 | Not conformity assessment or audit certification |
| CHANGE-01 | Prevent in-place redefinition of completed release | change policy + immutable-release CI verifier | NIST GOVERN/MANAGE; ISO change/accountability themes; EU Arts. 11–12 | Does not replace organizational CAB/RBAC/approvals |
| SCOPE-01 | Prevent governance overclaiming | governance docs/contracts | NIST GOVERN/MAP; ISO transparency/accountability; EU Art. 11 | Crosswalk itself is not compliance evidence |

## Current official references

- NIST AI Risk Management Framework 1.0 Core: <https://airc.nist.gov/airmf-resources/airmf/5-sec-core/>. NIST currently notes that a revised version is in progress.
- ISO/IEC 42001:2023 overview: <https://www.iso.org/standard/42001>. The public ISO description emphasizes an AI management system, risk management, traceability, transparency, reliability, accountability, and continual improvement.
- Regulation (EU) 2024/1689 consolidated text: <https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng>. Relevant crosswalk themes here are Article 10 (data and data governance), Article 11 (technical documentation), Article 12 (record-keeping), and Annex IV.

## Interview-safe summary

A precise description of this repository is:

> I implemented evidence-backed controls for dataset identity, acquisition provenance, train/test governance, prospective design locking, external preregistration, environment reproducibility, per-fit lineage, result integrity, independent release reconstruction, and frozen-study change control. I can map those controls to NIST AI RMF, ISO/IEC 42001 themes, and relevant EU AI Act governance concepts, but I would not present the repository itself as enterprise compliance, certification, RBAC, privacy governance, or production deployment governance.
