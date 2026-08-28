"""Analysis tests."""

import pandas as pd

from ml_reproducibility.analysis import (
    behavioural_reference_match_summary,
    factorial_anova,
    pairwise_reproducibility_curve,
    procedure_stability,
    reference_reproducibility_curve,
)


def test_factorial_anova_returns_per_model_sensitivity_shares() -> None:
    """Balanced synthetic factorial tables should produce finite per-model ANOVA shares."""

    rows: list[dict[str, object]] = []
    for model, model_effect in (("sgd_logistic", 0.0), ("random_forest", 0.002)):
        for split_seed in (1, 2):
            for model_seed in (10, 11):
                for preprocessing in ("standard", "none"):
                    rows.append(
                        {
                            "model": model,
                            "split_seed": split_seed,
                            "model_seed": model_seed,
                            "preprocessing": preprocessing,
                            "roc_auc": 0.80
                            + model_effect
                            + 0.01 * split_seed
                            + 0.001 * model_seed
                            + (0.005 if preprocessing == "standard" else 0.0),
                        }
                    )
    table = factorial_anova(pd.DataFrame(rows))
    assert "share_total_ss" in table.columns
    assert set(table["model"]) == {"sgd_logistic", "random_forest"}
    assert table["share_total_ss"].notna().all()


def test_reference_curve_excludes_the_reference_run() -> None:
    """The published reference must not count as a successful reproduction of itself."""

    frame = pd.DataFrame(
        [
            {
                "model": "logistic",
                "split_seed": 10,
                "model_seed": 20,
                "preprocessing": "standard",
                "roc_auc": 0.900,
            },
            {
                "model": "logistic",
                "split_seed": 11,
                "model_seed": 20,
                "preprocessing": "standard",
                "roc_auc": 0.904,
            },
            {
                "model": "logistic",
                "split_seed": 12,
                "model_seed": 20,
                "preprocessing": "standard",
                "roc_auc": 0.909,
            },
        ]
    )
    curve = reference_reproducibility_curve(
        frame,
        experiment="split_sensitivity",
        metric="roc_auc",
        tolerances=(0.005, 0.01),
    )
    assert curve.loc[curve["tolerance"] == 0.005, "n_replications"].item() == 2
    assert curve.loc[curve["tolerance"] == 0.005, "n_reproduced"].item() == 1
    assert curve.loc[curve["tolerance"] == 0.01, "n_reproduced"].item() == 2


def test_pairwise_curve_uses_all_distinct_run_pairs() -> None:
    """Pairwise reproducibility should compare all unordered distinct run pairs."""

    frame = pd.DataFrame(
        {
            "model": ["logistic"] * 3,
            "roc_auc": [0.900, 0.904, 0.909],
        }
    )
    curve = pairwise_reproducibility_curve(
        frame,
        experiment="split_sensitivity",
        metric="roc_auc",
        tolerances=(0.005,),
    )
    assert curve.loc[0, "n_pairs"] == 3
    assert curve.loc[0, "n_reproduced_pairs"] == 2


def test_procedure_stability_excludes_standard_reference() -> None:
    """Preprocessing is a finite alternative set rather than a sampling probability."""

    frame = pd.DataFrame(
        [
            {"model": "sgd_logistic", "preprocessing": "standard", "roc_auc": 0.90},
            {"model": "sgd_logistic", "preprocessing": "robust", "roc_auc": 0.904},
            {"model": "sgd_logistic", "preprocessing": "none", "roc_auc": 0.92},
        ]
    )
    result = procedure_stability(frame, metric="roc_auc", tolerances=(0.005,))
    assert result.loc[0, "n_alternative_procedures"] == 2
    assert result.loc[0, "n_within_tolerance"] == 1
    assert result.loc[0, "procedure_stability_fraction"] == 0.5


def test_behavioural_reference_match_excludes_reference_from_rate() -> None:
    """Identical classes can coexist with different continuous score vectors."""

    frame = pd.DataFrame(
        [
            {
                "model": "random_forest",
                "model_seed": 1,
                "preprocessing": "standard",
                "prediction_sha256": "a" * 64,
                "score_sha256": "b" * 64,
            },
            {
                "model": "random_forest",
                "model_seed": 2,
                "preprocessing": "standard",
                "prediction_sha256": "a" * 64,
                "score_sha256": "c" * 64,
            },
        ]
    )
    summary = behavioural_reference_match_summary(frame, experiment="seed_sensitivity")
    assert summary.loc[0, "n_nonreference"] == 1
    assert summary.loc[0, "unique_prediction_vectors_all_runs"] == 1
    assert summary.loc[0, "unique_score_vectors_all_runs"] == 2
    assert summary.loc[0, "exact_prediction_reference_match_rate"] == 1.0
    assert summary.loc[0, "exact_score_reference_match_rate"] == 0.0
