# Change control

This repository contains a completed, prospectively frozen scientific study. Change control therefore separates ordinary repository maintenance from changes that would create a new scientific specification.

## Scientific identity

The Adult release is externally anchored by immutable GitHub release `v0.7.1`. GitHub marks that release immutable and records a SHA-256 digest for the released preregistration capsule. The capsule embeds the complete Adult design lock, including every protected path and file digest.

A modification to any file in that anchored design lock is not a patch to the completed experiment. It requires a successor study with a new prospective freeze, preregistration capsule, immutable external anchor, fresh primary-data acquisition, fresh execution, and a new release decision.

Historical results are not re-labelled as results of the new specification.

## Historical evidence

Committed release artifacts and `results/adult/` are historical evidence. If a defect or deviation is discovered, the repository records that discovery additively and states its effect on the claims. Existing frozen evidence is not rewritten so that the completed study appears to have followed a later interpretation.

## Governance-only changes

Governance contracts, audit renderers, tests, and governance documentation may be strengthened without changing the experiment. These additions must remain grounded in committed evidence and must preserve explicit non-claims such as the absence of a production model registry, deployment lineage, RBAC, and persisted row-membership hashes.

## CI enforcement

`python scripts/verify_change_control.py` verifies the current tree against the immutable `v0.7.1` release before smoke execution. It:

1. retrieves the immutable release metadata and requires GitHub's `immutable` flag;
2. identifies the unique `adult_preregistration_capsule.json` release asset;
3. verifies the downloaded capsule against GitHub's recorded SHA-256 asset digest;
4. verifies the repository's local capsule and design-lock artifact against that external capsule;
5. verifies the governance policy and lineage contract agree with the externally anchored identities;
6. resolves every frozen path inside the repository root and rejects path escapes;
7. re-hashes every scientific file protected by the externally anchored design lock and fails on drift.

The verifier does not download Adult source data and does not execute any model. Its network dependency is deliberately limited to retrieving the immutable preregistration evidence that makes the check independent of values a pull request could rewrite locally.

## Why the external comparison matters

A self-check is not enough for change control. If expected hashes lived only in editable files in the same pull request, a contributor could alter a scientific file and update those expected hashes at the same time. Anchoring the check to immutable `v0.7.1` prevents that circular trust: the proposed change cannot redefine the historical release it is being compared against.
