"""Application settings, read from environment variables (no prefix)."""

from functools import cache
from typing import Annotated, Any, Literal

from fastapi import Depends, Request
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Our Alpaca request budget per minute. Alpaca allows 200 per key: prod has its own key,
# stage and the pull request previews share one.
_ALPACA_RATE_LIMITS = {"prod": 150, "stage": 60}
_ALPACA_RATE_LIMIT_PREVIEW = 30
_ALPACA_RATE_LIMIT_DEFAULT = 60


def default_alpaca_rate_limit(app_env: str) -> int:
    if app_env.startswith("pr-"):
        return _ALPACA_RATE_LIMIT_PREVIEW
    return _ALPACA_RATE_LIMITS.get(app_env, _ALPACA_RATE_LIMIT_DEFAULT)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore", frozen=True)

    app_env: str = Field(default="local", pattern=r"^(local|test|stage|prod|pr-\d+)$")
    app_version: str = "dev"
    app_commit: str = "unknown"
    log_level: LogLevel = "INFO"

    redis_url: str = "redis://127.0.0.1:6379/0"

    alpaca_key_id: SecretStr = SecretStr("")
    alpaca_secret_key: SecretStr = SecretStr("")
    alpaca_api_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"
    binance_api_url: str = "https://api.binance.com"
    binance_data_url: str = "https://data.binance.vision"

    candles_max: int = Field(default=50_000, gt=0)
    client_rate_limit: int = Field(default=60, ge=0)
    alpaca_rate_limit: int = Field(
        default_factory=lambda data: default_alpaca_rate_limit(data.get("app_env", "local")),
        gt=0,
    )
    binance_weight_limit: int = Field(default=1000, gt=0)

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("alpaca_key_id", "alpaca_secret_key", mode="before")
    @classmethod
    def _strip_key(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


@cache
def get_settings() -> Settings:
    """Settings of this process, read once from the environment."""
    return Settings()


def request_settings(request: Request) -> Settings:
    """Settings the running app was created with (see ``create_app``)."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(request_settings)]
