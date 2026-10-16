"""Response bodies of the accounts API (the contract the web app is built against)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Provider(StrEnum):
    """An identity provider a user signs in with."""

    github = "github"
    google = "google"


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
