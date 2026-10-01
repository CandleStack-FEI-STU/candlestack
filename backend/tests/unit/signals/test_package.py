from candlestack import signals


def test_root_has_every_name_of_its_public_api() -> None:
    """Other modules import signals only through the package root, so ``__all__`` is the API."""
    assert [name for name in signals.__all__ if not hasattr(signals, name)] == []
