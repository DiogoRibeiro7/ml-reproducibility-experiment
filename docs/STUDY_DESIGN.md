# Study design

## Research question

This repository studies reproducibility in a conventional **classical machine-learning** workflow.

The primary question is:

> When another researcher repeats an otherwise legitimate tabular-classification experiment, how much of the reported result changes because of the train/test split, estimator randomness, and preprocessing procedure?

The primary outcome is ROC-AUC. Accuracy, balanced accuracy and F1 are secondary descriptive outcomes.

## Primary dataset

The primary dataset is **Adult** from the UCI Machine Learning Repository (Becker & Kohavi, 1996; DOI `10.24432/C5XW20`). It contains 48,842 observations and 14 predictors with mixed categorical/integer variables and missing values.

The canonical `adult.data` and `adult.test` source bytes are SHA-256 pinned. The files are combined for repeated stratified hold-out experiments so that split choice itself is an experimental factor.

All 14 predictors are used as supplied, including `fnlwgt` (a survey sampling weight rather than a covariate) and the redundant `education`/`education_num` pair. Neither is defensible as feature engineering, and both are retained deliberately: they are what the conventional benchmark usage of this dataset does, and the object of study is that conventional workflow rather than an optimal model.

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

For every model, hold estimator seed and preprocessing fixed and vary only the stratified train/test split across 100 seeds:

\[
s\in\{1729,\ldots,1828\}.
\]

The reference split is 1729. It is **not** counted as a successful reproduction of itself.

Changing the split seed changes the training set and the test set together, so the variation this experiment measures is the **joint** effect of refitting on different data and evaluating on a different sample. That is deliberate: it is what a second researcher who re-splits actually experiences, and it is the quantity a reported number is exposed to. It is not a decomposition into estimation variance and evaluation variance, and it should not be read as one. Because the test set moves between runs, exact behavioural comparison is undefined here and is restricted to the families that hold the test set fixed.

## Experiment B: estimator-seed sensitivity

Hold the split and preprocessing fixed and vary the estimator random state across 100 seeds:

\[
r\in\{2718,\ldots,2817\}.
\]

The reference model seed is 2718. It is excluded from the reference-conditioned reproduction denominator.

Two of the four estimators have no stochastic component under this design: logistic regression is fitted with a deterministic solver, and the linear SVM has its internal random state pinned so that it acts as a low-randomness control. Their seed reruns reproduce **by construction**, not as an empirical finding. Rows for those estimators are flagged `deterministic_by_construction` so a rate of 1.0 is not read as an estimate. They remain in the design because they are what makes an apparent reproduction failure elsewhere attributable to the estimator rather than to the harness.

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

Sums of squares are reported with their share of the total. F ratios and p-values are
**not** reported. With one observation per cell the residual line is the unmodelled
three-way interaction rather than replication error, so ratios formed against it would not
be tests of anything. Reporting them would invite exactly the confirmatory reading the
design disclaims.


## Reference-conditioned reproducibility

For a prospectively fixed reference result \(m_0\), the split and seed experiments estimate

\[
R_{0}(\varepsilon)
=
P\left(|M-m_0|\leq\varepsilon\mid m_0\right).
\]

The original reference observation is excluded. With 100 configured runs, the denominator is therefore 99 genuine reruns.

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

## Precision of the reproducibility estimands

The reference-conditioned rate is a proportion over genuine reruns, so it carries sampling
error that a bare point estimate hides. Every reproduction rate is therefore reported with
an interval.

For \(R_0(\varepsilon)\) the reruns are independent given the reference, and the interval is
a 95% Wilson score interval. The Wald interval is unusable here because reproduction rates
sit at or near 0 and 1, where it collapses to zero width or leaves the unit interval.

For \(R_{\mathrm{pair}}(\varepsilon)\) the pairs are **not** independent: each run appears in
\(n-1\) of the \(\binom{n}{2}\) pairs. Treating the pair count as a sample size would badly
overstate precision. The interval is a delete-one-**run** jackknife, which resamples the
unit that actually varies.

The repetition count follows from this. At 30 configured runs the worst-case half-width of
the 95% interval is 0.171, wide enough that a rate of 0.35 and a rate of 0.65 are not
distinguishable. At 100 configured runs it is 0.097:

| configured runs | genuine reruns | worst-case 95% half-width |
|---|---|---|
| 30 | 29 | 0.171 |
| 100 | 99 | 0.097 |

The design therefore uses 100 split repetitions and 100 estimator-seed repetitions. The
cost is concentrated almost entirely in the random forest, whose fits dominate runtime; the
remaining estimators are cheap enough that the increase is negligible for them.

Procedure stability is **not** given an interval. It is a fraction over a finite declared
set of procedures, not an estimate of a population quantity, and attaching sampling
uncertainty to a complete enumeration would misrepresent it.


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

## Score degeneracy is recorded, not assumed away

ROC-AUC is a rank statistic, so the quantity that matters is whatever the estimator ranks
by. The study uses `decision_function` where an estimator provides one and the positive
class probability otherwise. That choice is not cosmetic. Fitted on unscaled features, a
linear model can drive margins to magnitudes around \(10^{7}\); the logistic link then
saturates and every predicted probability collapses onto \(\{0,1\}\). The ranking survives
in the margin and is destroyed in the probability.

This failure emits **no convergence warning**. Reviewing the design before freezing, an
unscaled SGD fit on data at Adult's numeric scale was observed to converge cleanly by the
optimiser's own criterion while returning as few as one distinct probability across the
whole test set. Had the study ranked on probabilities it would have reported a
tie-dominated ROC-AUC, and two materially different fits would have shared a score
signature, silently corrupting the behavioural comparison.

Every fit therefore records:

```text
score_kind          which quantity was ranked
n_unique_scores     distinct values in the score vector
score_abs_median    median absolute score
```

A collapsed `n_unique_scores` or an enormous `score_abs_median` is an observed outcome of
a preprocessing procedure, in exactly the sense that a convergence failure is. It is
reported, not repaired.

## Duplicate records

Adult contains exact duplicate records. Combining `adult.data` with `adult.test` and
re-splitting can therefore place copies of one record on both sides of a split, which
inflates every metric slightly.

The declared procedure **retains** duplicates, because a conventional workflow does and the
study is about conventional workflows. The counts are recorded as dataset provenance
(`n_duplicate_feature_rows`, `n_duplicate_labelled_rows`) so the magnitude of the effect is
an observed, preregistered quantity rather than an unexamined assumption. Because the
optimism applies to every run alike, it shifts the level of the metrics without being a
plausible driver of the between-run variation the study measures.


## Numerical execution policy

The canonical primary run fixes:

\[
\texttt{n\_jobs}=1,
\qquad
\texttt{numeric\_threads}=1.
\]

Numerical kernels are constrained at execution through `threadpoolctl`. Python and package versions are prospectively pinned in `environment/runtime-policy.json` and `environment/requirements.lock.txt`, both of which are included in the design hash.

## What reproduces where

The study distinguishes three levels of agreement, because they do not travel together across machines.

| Quantity | Portable across platforms |
|---|---|
| ROC-AUC and the other aggregate metrics | yes, to well under the smallest declared tolerance |
| every derived analysis table | yes, byte-for-byte |
| per-fit prediction and score SHA-256 signatures | **no** |

Continuous scores differ in their final floating-point bits between BLAS builds, so `score_sha256` is a signature of one numerical environment rather than of the statistical procedure. The canonical platform is declared in `environment/runtime-policy.json`.

This matters for how a failed replication is read. A rerun on different hardware that reproduces every derived table but differs in score signatures has reproduced the study's conclusions and not its bytes. That is a platform difference, and the protocol requires it to be reported as such rather than as a failed reproduction.


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
4\times100=400
\]

split-sensitivity fits,

\[
4\times100=400
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
\boxed{1196\ \text{primary model fits}}.
\]

No configured run may be removed because it is slow, inconvenient, unusually strong, unusually weak, or fails to converge.

## Scope

The study distinguishes data-split variation, algorithmic randomness, and procedural sensitivity, while separating metric reproduction from behavioural replay. It does not claim that one dataset or four estimators define reproducibility for all machine learning.
