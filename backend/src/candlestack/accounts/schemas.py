"""Response bodies of the accounts API (the contract the web app is built against)."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Provider(StrEnum):
    """An identity provider a user signs in with."""

    github = "github"
    google = "google"


class SignInIntent(StrEnum):
    sign_in = "sign-in"
    connect = "connect"


class MeOut(BaseModel):
    """The signed-in user."""

    id: str = Field(
        pattern=r"^usr_[a-z0-9]{10}$",
        description="Public user ID, shown in Settings and given to support",
        examples=["usr_7f3k2m9qx4"],
    )
    display_name: str = Field(description="Name shown in the app", examples=["Arsen Labovich"])
    email: str = Field(
        description="From the identity provider, read-only", examples=["arsen@example.com"]
    )
    providers: list[Provider] = Field(
        description="Connected sign-in methods", examples=[["github"]]
    )
    created_at: datetime = Field(description="When the account was created (UTC)")


class DeniedSignInOut(BaseModel):
    """The last sign-in of this browser that the beta list turned away."""

    email: str = Field(description="The account's email", examples=["arsen@example.com"])
    provider: Provider


class MeUpdate(BaseModel):
    """What the user may change about themselves."""

    display_name: str = Field(
        min_length=1,
        max_length=80,
        description="Name shown in the app; surrounding whitespace is dropped",
        examples=["Arsen Labovich"],
    )


class Timeframe(StrEnum):
    """Timeframes a new backtest can start with (Settings, Backtest defaults)."""

    m5 = "5m"
    m30 = "30m"
    h1 = "1h"
    d1 = "1d"


class Direction(StrEnum):
    long = "long"
    both = "both"


class Benchmark(StrEnum):
    """What each backtest is measured against: buy and hold of its own instruments, or an ETF."""

    buy_and_hold = "bh"
    spy = "SPY"
    qqq = "QQQ"
    dia = "DIA"


class BacktestDefaults(BaseModel):
    """How new backtests start (Settings, Backtest defaults)."""

    timeframe: Timeframe = Timeframe.m30
    period_start: date = Field(default=date(2021, 1, 4), description="First day of the test")
    period_end: date = Field(default=date(2024, 12, 31), description="Last day of the test")
    direction: Direction = Direction.long
    threshold: float = Field(
        default=0.05, ge=0, le=0.5, multiple_of=0.01, description="Signal strength to trade"
    )
    stop_loss_pct: int = Field(
        default=7, ge=1, le=20, description="Exit when a trade loses this many percent"
    )
    fees_pct: float = Field(default=0.1, ge=0, le=5, description="Fees in percent per side")
    slippage_pct: float = Field(default=0.02, ge=0, le=5, description="Slippage in percent")
    benchmark: Benchmark = Benchmark.buy_and_hold


class Theme(StrEnum):
    light = "light"
    dark = "dark"


class TimeZone(StrEnum):
    """`ny`: exchange time (New York); `local`: the browser's time zone."""

    ny = "ny"
    local = "local"


class DateFormat(StrEnum):
    """`dmy` 12 Oct 2024, `iso` 2024-10-12, `dot` 12.10.2024."""

    dmy = "dmy"
    iso = "iso"
    dot = "dot"


class TimeFormat(StrEnum):
    """`24` 16:05, `12` 4:05 PM."""

    h24 = "24"
    h12 = "12"


class Appearance(BaseModel):
    """How the app looks for this user (Settings, Appearance)."""

    theme: Theme = Theme.dark
    time_zone: TimeZone = TimeZone.ny
    date_format: DateFormat = DateFormat.dmy
    time_format: TimeFormat = TimeFormat.h24
    reduce_motion: bool = Field(default=False, description="Turns off the small animations")


class AppearanceUpdate(BaseModel):
    """A change of some of the appearance settings; the fields left out stay."""

    theme: Theme | None = None
    time_zone: TimeZone | None = None
    date_format: DateFormat | None = None
    time_format: TimeFormat | None = None
    reduce_motion: bool | None = None


class PreferencesOut(BaseModel):
    """The user's settings; a user who never saved any gets the defaults."""

    backtest_defaults: BacktestDefaults
    appearance: Appearance
