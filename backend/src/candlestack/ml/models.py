"""The table of the models users upload; their files live in the model storage
(``storage.py``). Changed only through migrations (``backend/migrations``)."""

import secrets
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from candlestack.core import Base

# The alphabet of the user IDs (lowercase RFC 4648 base32: no 0, 1, 8 or 9), so the IDs of the
# app read alike.
_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
_ID_LENGTH = 10


def new_model_id() -> str:
    """A public model ID such as ``mdl_7f3k2m9qx4`` (50 random bits)."""
    return "mdl_" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(_ID_LENGTH))


class Model(Base):
    """An uploaded model: what its file holds, as the upload check read it. The file is at
    ``<user_id>/<id>.keras`` in the model storage."""

    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(14), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # The file name, extension included.
    name: Mapped[str] = mapped_column(String(255))
    framework: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    # The SHA-256 of the file, which backtests will name the model by.
    sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    parameters: Mapped[int] = mapped_column(BigInteger)
    input_shape: Mapped[list[int] | None] = mapped_column(JSONB)
    output_shape: Mapped[list[int] | None] = mapped_column(JSONB)
    keras_version: Mapped[str] = mapped_column(String(32))
    starred: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# A user's names are unique in any case, as the numbering of uploads compares them so.
Index("uq_models_user_id_name", Model.user_id, func.lower(Model.name), unique=True)
