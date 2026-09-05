# Change control

This repository contains a completed, prospectively frozen scientific study. Change control therefore separates ordinary repository maintenance from changes that would create a new scientific specification.

## Scientific identity

The Adult release is identified by the committed design lock and its SHA-256 digest. Every path listed in `artifacts/adult_design_lock.json` is part of that frozen identity. A modification to any of those files is not a patch to the completed experiment: it requires a successor study with a new prospective freeze, preregistration capsule, immutable external anchor, fresh primary-data acquisition, fresh execution, and a new release decision.

Historical results are not re-labelled as results of the new specification.

## Historical evidence

Committed release artifacts and `results/adult/` are historical evidence. If a defect or deviation is discovered, the repository records that discovery additively and states its effect on the claims. Existing frozen evidence is not rewritten so that the completed study appears to have followed a later interpretation.

## Governance-only changes

Governance contracts, audit renderers, tests, and governance documentation may be strengthened without changing the experiment. These additions must remain grounded in committed evidence and must preserve explicit non-claims such as the absence of a production model registry, deployment lineage, RBAC, and persisted row-membership hashes.

## CI enforcement

`python scripts/verify_change_control.py` verifies the frozen boundary offline. It checks that:

1. the committed Adult design-lock artifact still has the release SHA-256 declared by governance;
2. the lineage contract agrees with that design identity;
3. every scientific file protected by the Adult design lock exists and still matches its frozen SHA-256.

This check deliberately requires no Adult source-data download. It protects the scientific specification before any data acquisition or model execution occurs.
