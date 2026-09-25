import pytest
from pydantic import ValidationError

from candlestack.core import Settings, get_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_defaults() -> None:
    settings = Settings()

    assert settings.app_env == "local"
    assert settings.app_version == "dev"
    assert settings.app_commit == "unknown"
    assert settings.log_level == "INFO"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.alpaca_key_id.get_secret_value() == ""
    assert settings.alpaca_secret_key.get_secret_value() == ""
    assert settings.alpaca_api_url == "https://paper-api.alpaca.markets"
    assert settings.alpaca_data_url == "https://data.alpaca.markets"
    assert settings.binance_api_url == "https://api.binance.com"
    assert settings.binance_data_url == "https://data.binance.vision"
    assert settings.candles_max == 50_000
    assert settings.client_rate_limit == 60
    assert settings.alpaca_rate_limit == 60
    assert settings.binance_weight_limit == 1000


@pytest.mark.parametrize(
    ("app_env", "limit"),
    [("prod", 150), ("stage", 60), ("pr-42", 30), ("local", 60), ("test", 60)],
)
def test_alpaca_rate_limit_default_depends_on_env(
    monkeypatch: pytest.MonkeyPatch, app_env: str, limit: int
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)

    assert Settings().alpaca_rate_limit == limit


def test_alpaca_rate_limit_default_follows_init_arguments() -> None:
    assert Settings(app_env="pr-7").alpaca_rate_limit == 30


def test_alpaca_rate_limit_can_be_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ALPACA_RATE_LIMIT", "100")

    assert Settings().alpaca_rate_limit == 100


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "stage")
    monkeypatch.setenv("APP_VERSION", "main-abc")
    monkeypatch.setenv("CANDLES_MAX", "1000")
    monkeypatch.setenv("CLIENT_RATE_LIMIT", "0")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings()

    assert settings.app_env == "stage"
    assert settings.app_version == "main-abc"
    assert settings.candles_max == 1000
    assert settings.client_rate_limit == 0
    assert settings.log_level == "DEBUG"


def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CANDLES_MAX", "")
    monkeypatch.setenv("ALPACA_RATE_LIMIT", "")

    settings = Settings()

    assert settings.candles_max == 50_000
    assert settings.alpaca_rate_limit == 60


def test_alpaca_keys_are_stripped_and_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_KEY_ID", "  PKTEST123 \n")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "\tsecret456  ")

    settings = Settings()

    assert settings.alpaca_key_id.get_secret_value() == "PKTEST123"
    assert settings.alpaca_secret_key.get_secret_value() == "secret456"
    assert "PKTEST123" not in repr(settings)
    assert "secret456" not in repr(settings)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_ENV", "staging"),
        ("APP_ENV", "pr-"),
        ("LOG_LEVEL", "LOUD"),
        ("CANDLES_MAX", "0"),
        ("CLIENT_RATE_LIMIT", "-1"),
    ],
)
def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_is_read_once() -> None:
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
