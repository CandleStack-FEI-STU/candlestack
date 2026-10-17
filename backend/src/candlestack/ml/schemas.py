"""Request and response bodies of the models API."""

import unicodedata
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The name of a model without its extension, as the Rename dialog edits it.
NAME_MAX = 60
# Limits of the uploaded files (binary megabytes, as the app shows them).
MB = 1024 * 1024
FILE_MAX_BYTES = 50 * MB
QUOTA_BYTES = 100 * MB
# Models a user may keep.
MODELS_MAX = 100
# Unicode categories a name never holds: control and format characters (bidirectional
# overrides, zero-width spaces), which make a name read other than it is.
_INVISIBLE = frozenset({"Cc", "Cf"})


def without_invisible(text: str) -> str:
    """`text` without control and format characters."""
    return "".join(char for char in text if unicodedata.category(char) not in _INVISIBLE)


class Framework(StrEnum):
    """The framework a model file belongs to; only Keras is accepted for now."""

    keras = "keras"


class ModelCheck(StrEnum):
    """The checks of an upload, in the order they run: `opens` (a real model of its format with
    no custom code inside), then `weights` (it holds trained weights)."""

    opens = "opens"
    weights = "weights"


class ModelOut(BaseModel):
    id: str = Field(description="Public ID of the model", examples=["mdl_7f3k2m9qx4"])
    name: str = Field(
        description="File name, extension included; Rename changes only the part before it",
        examples=["my-tsmixer.keras"],
    )
    framework: Framework
    size_bytes: int = Field(description="Size of the file", examples=[14_889_779])
    parameters: int = Field(description="Number of weights in the file", examples=[1_240_000])
    input_shape: list[int] | None = Field(
        description=(
            "Shape of one input sample without the batch dimension, e.g. 25 candles by 23 "
            "features; null when the file does not say"
        ),
        examples=[[25, 23]],
    )
    output_shape: list[int] | None = Field(
        description="Shape of one output without the batch dimension; null when unknown",
        examples=[[1]],
    )
    starred: bool = Field(description="The user starred the model")
    backtest_count: int = Field(
        description="Backtests that used the model, failed ones included; 0 until backtests exist",
        examples=[0],
    )
    best_sharpe: float | None = Field(
        description="Best Sharpe ratio of its finished backtests; null without one",
        examples=[None],
    )
    created_at: datetime = Field(description="When the model was uploaded (UTC)")


class StorageUsage(BaseModel):
    used_bytes: int = Field(description="Bytes taken by the user's uploaded models", examples=[0])
    quota_bytes: int = Field(
        description="Bytes the user's uploaded models may take", examples=[QUOTA_BYTES]
    )
    file_max_bytes: int = Field(
        description="Largest file an upload takes", examples=[FILE_MAX_BYTES]
    )


class ModelsOut(BaseModel):
    models: list[ModelOut] = Field(description="The user's models, oldest first")
    usage: StorageUsage


class ModelUpdate(BaseModel):
    """What Rename and the star change; a field left out stays as it is."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=NAME_MAX,
        pattern=r"^[^/\\\x00-\x1f\x7f]+$",
        description=(
            "New name without the extension, which stays; no slashes, control or format "
            "characters (Unicode Cc and Cf)"
        ),
        examples=["tsmixer-v2"],
    )
    starred: bool | None = Field(default=None, description="Star or unstar the model")

    @field_validator("name")
    @classmethod
    def _visible(cls, name: str | None) -> str | None:
        if name is not None and without_invisible(name) != name:
            raise ValueError("must not hold control or format characters")
        return name
