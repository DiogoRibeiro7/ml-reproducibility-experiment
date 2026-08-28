"""Dataset-loading tests."""

from ml_reproducibility.data import load_breast_cancer_smoke


def test_smoke_dataset_shape_and_binary_target() -> None:
    """The offline validation dataset must have stable dimensions and labels."""

    bundle = load_breast_cancer_smoke()
    assert bundle.X.shape == (569, 30)
    assert set(bundle.y.unique()) == {0, 1}
    assert isinstance(bundle.provenance["canonical_array_sha256"], str)
