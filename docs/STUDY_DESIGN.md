# Study design

## Research question

This repository studies reproducibility in a conventional **classical machine-learning** workflow.

The primary question is:

> When another researcher repeats an otherwise legitimate tabular-classification experiment, how much of the reported result changes because of the train/test split, estimator randomness, and preprocessing procedure?

The primary outcome is ROC-AUC. Accuracy, balanced accuracy and F1 are secondary descriptive outcomes.

## Primary dataset

The primary dataset is **Adult** from the UCI Machine Learning Repository (Becker & Kohavi, 1996; DOI `10.24432/C5XW20`). It contains 48,842 observations and 14 predictors with mixed categorical/integer variables and missing values.

The canonical `adult.data` and `adult.test` source bytes are SHA-256 pinned. The files are combined for repeated stratified hold-out experiments so that split choice itself is an experimental factor.

## Models

| Model | Experimental role |
|---|---|
| Logistic regression | low-randomness control |
| Linear SVM | low-randomness control |
| Random forest | stochastic ensemble |
| SGD logistic classifier | stochastic and scale-sensitive estimator |

The deterministic controls must remain invariant when only the irrelevant model-seed label changes.

## Preprocessing procedures

All preprocessing is fitted inside the training pipeline. The predeclared procedures are:

1. median numerical imputation + standard scaling;
2. median numerical imputation + robust scaling;
3. median numerical imputation without scaling.

Categorical predictors use most-frequent imputation and one-hot encoding. `standard` is the reference procedure.

## Experiment A: split sensitivity

For every model, hold estimator seed and preprocessing fixed and vary only the stratified train/test split across 30 seeds:

\[
s\in\{1729,\ldots,1758\}.
\]

The reference split is 1729. It is **not** counted as a successful reproduction of itself.

## Experiment B: estimator-seed sensitivity

Hold the split and preprocessing fixed and vary the estimator random state across 30 seeds:

\[
r\in\{2718,\ldots,2747\}.
\]

The reference model seed is 2718. It is excluded from the reference-conditioned reproduction denominator.

## Experiment C: preprocessing sensitivity

Hold split and model seed fixed while changing among the three declared preprocessing procedures.

These procedures are fixed scenarios, not random draws from a population of procedures. The analysis therefore reports a **procedure-stability fraction**, not a probability.

## Experiment D: crossed stochastic-estimator sensitivity

Both stochastic estimators are crossed over the same design:

\[
8\ \text{split levels}
\times
8\ \text{model-seed levels}
\times
3\ \text{preprocessing procedures}
\times
2\ \text{models}
=
384\ \text{fits}.
\]

The models are Random Forest and SGD Logistic. For each model separately, the descriptive ANOVA is

\[
Y_{srp}=\mu+\alpha_s+\beta_r+\gamma_p
+(\alpha\beta)_{sr}
+(\alpha\gamma)_{sp}
+(\beta\gamma)_{rp}
+\varepsilon_{srp}.
\]

With one observation per split × seed × procedure cell, the residual contains the three-way interaction. ANOVA sums of squares are descriptive sensitivity attribution, not confirmatory significance tests.

## Reference-conditioned reproducibility

For a prospectively fixed reference result \(m_0\), the split and seed experiments estimate

\[
R_{0}(\varepsilon)
=
P\left(|M-m_0|\leq\varepsilon\mid m_0\right).
\]

The original reference observation is excluded. With 30 configured runs, the denominator is therefore 29 genuine reruns.

The fixed ROC-AUC tolerances are

\[
\boxed{0.001,\quad0.005,\quad0.010}.
\]

## Pairwise reproducibility

The study also estimates an intrinsic two-run quantity:

\[
R_{\mathrm{pair}}(\varepsilon)
=
P\left(|M_1-M_2|\leq\varepsilon\right),
\]

using every unordered pair of legitimate split or seed runs. This separates reproducibility of an arbitrary published reference from reproducibility between two independently legitimate executions.

## Behavioural reproduction

Every run records SHA-256 signatures of the predicted class vector and continuous score vector. Exact behavioural comparison is made only when test observations are fixed: model-seed sensitivity and preprocessing sensitivity.

The reference row is again excluded from the matching rate. Therefore

\[
\text{same ROC-AUC}
\not\Rightarrow
\text{same predicted classes}
\not\Rightarrow
\text{same continuous scores}.
\]

## Convergence as an observed outcome

Iterative estimators record:

- `converged`;
- `convergence_warning_count`;
- `n_iter`.

A convergence failure is not silently removed. In particular, failure of unscaled SGD to converge is itself a possible procedural-reproducibility outcome.

## Numerical execution policy

The canonical primary run fixes:

\[
\texttt{n\_jobs}=1,
\qquad
\texttt{numeric\_threads}=1.
\]

Numerical kernels are constrained at execution through `threadpoolctl`. Python and package versions are prospectively pinned in `environment/runtime-policy.json` and `environment/requirements.lock.txt`, both of which are included in the design hash.

## Prospective publication boundary

The primary design is externally anchored through a deterministic preregistration capsule. The capsule contains the verified design-lock payload, configuration hash, pinned Adult source-byte policy, primary metric, tolerances, models, procedures and exact family fit counts.

Capsule construction is permitted only while canonical Adult source bytes and Adult empirical outputs are absent. The exact capsule bytes must then be published externally and retrieved back over HTTPS before data acquisition is authorised. Adult acquisition receipts and all subsequent empirical manifests bind the verified anchor identity.

This separates three claims that are often conflated:

\[
\text{design fixed locally}
\neq
\text{design externally published}
\neq
\text{empirical result reproduced}.
\]

## Prospective run count

The Adult study contains:

\[
4\times30=120
\]

split-sensitivity fits,

\[
4\times30=120
\]

seed-sensitivity fits,

\[
4\times3=12
\]

preprocessing fits, and

\[
2\times8\times8\times3=384
\]

crossed-factorial fits.

The total is therefore

\[
\boxed{636\ \text{primary model fits}}.
\]

No configured run may be removed because it is slow, inconvenient, unusually strong, unusually weak, or fails to converge.

## Scope

The study distinguishes data-split variation, algorithmic randomness, and procedural sensitivity, while separating metric reproduction from behavioural replay. It does not claim that one dataset or four estimators define reproducibility for all machine learning.
