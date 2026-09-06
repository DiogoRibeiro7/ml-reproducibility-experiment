# Governance risk register

This document summarises the evidence-backed risk register in `governance/risk_register.json`.
It describes risks visible in the completed Adult reproducibility study and the controls that
mitigate or bound them. It is not an enterprise risk-acceptance record: this repository does
not contain evidence for organizational owners, appetite thresholds, approval authorities,
or formal likelihood/impact scoring.

| Risk | Theme | Treatment | Residual state | Main controls |
|---|---|---|---|---|
| RISK-01 | Single external anchor | Mitigate | Open | DESIGN-02, CHANGE-01 |
| RISK-02 | Cross-platform numerical divergence | Document | Mitigated, not eliminated | EXEC-01, ASSURE-01 |
| RISK-03 | No persisted row-membership digests / validation registry | Document | Bounded by scope | PART-01, SCOPE-01 |
| RISK-04 | No production model registry or deployment lineage | Document | Bounded by scope | LINEAGE-01, SCOPE-01 |
| RISK-05 | One dataset / four estimators | Successor study | Open | ASSURE-01, SCOPE-01 |
| RISK-06 | No enterprise RBAC/privacy/retention/deployment controls | Document | Bounded by scope | SCOPE-01 |
| RISK-07 | Framework crosswalk could be mistaken for compliance | Mitigate | Mitigated, not eliminated | SCOPE-01 |
| RISK-08 | Later repository change could redefine the frozen release | Mitigate | Mitigated, not eliminated | CHANGE-01, DESIGN-02 |

## What is actually treated

The strongest repository-level mitigations are cryptographic identity, externally anchored
preregistration, deterministic partition and fit lineage, independent release reconstruction,
and CI change control against the immutable `v0.7.1` release.

Those controls materially reduce ambiguity about what was run and what evidence belongs to
the completed release. They do not eliminate every risk. In particular, a second independent
archive is still missing; strict score hashes remain platform-sensitive; and the study does
not contain the enterprise lifecycle controls of a production MLOps platform.

## What is deliberately not invented

The register does not assign numeric likelihood or impact scores, name organizational risk
owners, mark risks as formally accepted, or assert that any organization has approved a
residual risk. Those would be governance records in their own right and are not evidenced by
this research repository.

For interview purposes, the useful distinction is:

```text
identified risk
+ concrete repository evidence
+ implemented mitigation
+ explicit residual boundary
!=
formal organizational risk acceptance
```

That distinction is important in responsible AI governance: good controls do not justify
claiming assurance that has not actually been performed.
