from candlestack import metrics


def test_root_has_every_name_of_its_public_api() -> None:
    """Other modules import metrics only through the package root, so ``__all__`` is the API."""
    assert [name for name in metrics.__all__ if not hasattr(metrics, name)] == []
