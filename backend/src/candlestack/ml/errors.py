"""Errors of the models service. They know nothing about HTTP: the API turns each into its
problem."""

from candlestack.ml.schemas import ModelCheck


class UnsupportedModelFormat(Exception):
    """The file is not a Keras model (``.keras``), the only format taken for now."""


class ModelTooLarge(Exception):
    """The file is larger than an upload may be."""


class StorageFull(Exception):
    """The file does not fit into the user's storage."""

    def __init__(self, used_bytes: int, quota_bytes: int) -> None:
        super().__init__(f"{used_bytes} of {quota_bytes} bytes taken")
        self.used_bytes = used_bytes
        self.quota_bytes = quota_bytes


class ModelCheckFailed(Exception):
    """A check of the uploaded file failed: ``check`` names it, ``detail`` tells the user what
    is wrong with the file and what to do, in plain words."""

    def __init__(self, check: ModelCheck, detail: str) -> None:
        super().__init__(f"{check}: {detail}")
        self.check = check
        self.detail = detail


class ModelNotFound(Exception):
    """The user has no model with the ID (another user's model included)."""


class ModelNameTaken(Exception):
    """The user has another model with the name."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name
