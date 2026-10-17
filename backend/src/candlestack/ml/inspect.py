"""The static check of an uploaded Keras file: what the file holds, read without loading it.

A ``.keras`` file is a zip of ``config.json`` (the architecture), ``metadata.json`` (the Keras
version) and ``model.weights.h5`` (the weights, HDF5), with optional ``assets/``. Loading it
with Keras could run code from the file (a ``Lambda`` layer is pickled Python, a custom layer
is the user's class), so the API never imports Keras: it reads the JSON and the HDF5 metadata
only, and rejects anything a load would have to run code for. Two checks, in order:

- ``opens``: a real Functional or Sequential Keras model with nothing unsafe in the zip and no
  custom code in the architecture. What only shapes or reports training is ignored: the
  ``compile_config`` (optimizer, loss, metrics) and the ``*_regularizer`` and ``*_constraint``
  objects, which a prediction never needs (the worker loads those with a stub).
- ``weights``: the weights file reads as HDF5 and holds weights of the layers (not only the
  optimizer's state).

Pure functions on a file path: no I/O besides reading the file and unpacking its weights to the
scratch path the caller gives.
"""

import json
import math
import re
import shutil
import struct
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import h5py

from candlestack.ml.errors import ModelCheckFailed
from candlestack.ml.schemas import FILE_MAX_BYTES, MB, ModelCheck

CONFIG = "config.json"
METADATA = "metadata.json"
WEIGHTS = "model.weights.h5"
_MEMBERS = frozenset({CONFIG, METADATA, WEIGHTS})
_ASSETS = "assets/"
# A zip bomb unpacks to far more than it weighs; no real model needs more than this.
UNPACKED_MAX = 4 * FILE_MAX_BYTES
JSON_MAX = 5 * MB
# Postgres' bigint, the column the count goes to.
_PARAMETERS_MAX = 2**63 - 1
_KERAS_VERSION_MAX = 32

_MODEL_CLASSES = frozenset({"Functional", "Sequential"})
# Layers that hold Python code (a lambda, an op of TensorFlow) instead of configuration.
_CODE_LAYERS = frozenset({"Lambda", "TFOpLambda", "SlicingOpLambda", "__lambda__"})
# Keys whose objects only shape or report training: skipped by the custom code check.
_TRAINING_ONLY = "compile_config"
_TRAINING_ONLY_SUFFIXES = ("_regularizer", "_constraint")
# Layers whose output has the shape of their input.
_SHAPE_KEEPING = frozenset(
    {
        "Activation",
        "ActivityRegularization",
        "AlphaDropout",
        "BatchNormalization",
        "Dropout",
        "ELU",
        "GaussianDropout",
        "GaussianNoise",
        "GroupNormalization",
        "Identity",
        "LayerNormalization",
        "LeakyReLU",
        "Masking",
        "PReLU",
        "ReLU",
        "Softmax",
        "UnitNormalization",
    }
)
# What a damaged or foreign zip raises while it is read.
_ZIP_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    NotImplementedError,
    RuntimeError,
    ValueError,
    struct.error,
)
# What h5py raises on a file that is not HDF5 or is damaged inside.
_HDF5_ERRORS = (OSError, KeyError, RuntimeError, ValueError, TypeError)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SHOWN_MAX = 60

_SAVE_AGAIN = 'Save the model again with model.save("model.keras") and upload that file.'
_BROKEN = (
    "The file is not a readable Keras model. It may be damaged or not a .keras file at all. "
    + _SAVE_AGAIN
)
_NO_WEIGHTS = "The file holds the layers only. Save the model after training and upload that file."


@dataclass(frozen=True, slots=True)
class ModelFacts:
    """What the check read from a file that passed it."""

    keras_version: str
    parameters: int
    input_shape: list[int] | None
    output_shape: list[int] | None


def inspect_keras(path: Path, scratch: Path) -> ModelFacts:
    """Checks the Keras file at `path` without running anything from it and returns what it
    holds. The weights are unpacked to `scratch` to be read; the caller removes that file.

    Raises:
        ModelCheckFailed: A check failed; its ``detail`` tells the user why.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            _check_members(archive)
            keras_version = _keras_version(_read_json(archive, METADATA))
            config = _read_json(archive, CONFIG)
            _check_architecture(config)
            # zipfile reads no more than the size the archive declares, which is capped above.
            with archive.open(WEIGHTS) as source, scratch.open("wb") as target:
                shutil.copyfileobj(source, target)
    except _ZIP_ERRORS as error:
        raise _opens(_BROKEN) from error
    parameters = count_parameters(scratch)
    layers = _layers(config)
    return ModelFacts(
        keras_version=keras_version,
        parameters=parameters,
        input_shape=_input_shape(layers),
        output_shape=_output_shape(config, layers),
    )


def _opens(detail: str) -> ModelCheckFailed:
    return ModelCheckFailed(ModelCheck.opens, detail)


def _weights(detail: str) -> ModelCheckFailed:
    return ModelCheckFailed(ModelCheck.weights, detail)


def _check_members(archive: zipfile.ZipFile) -> None:
    """Fails unless the zip holds the three files of a Keras model, nothing outside it and
    nothing but assets besides, and unpacks to a size a model may have."""
    infos = archive.infolist()
    for info in infos:
        name = info.filename
        if (
            name.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", name)
            or ".." in PurePosixPath(name.replace("\\", "/")).parts
        ):
            raise _opens("The file holds a path that points outside the model. " + _SAVE_AGAIN)
        if name not in _MEMBERS and not name.startswith(_ASSETS):
            raise _opens("The file holds files a Keras model does not have. " + _SAVE_AGAIN)
    missing = sorted(_MEMBERS - {info.filename for info in infos})
    if missing:
        raise _opens(
            f"The file has no {missing[0]}, so it is not a whole Keras model. " + _SAVE_AGAIN
        )
    if sum(info.file_size for info in infos) > UNPACKED_MAX:
        raise _opens(
            f"The file unpacks to more than {UNPACKED_MAX // MB} MB, more than any model "
            "CandleStack takes. Upload a smaller model."
        )


def _read_json(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    """The JSON object in `member`."""
    if archive.getinfo(member).file_size > JSON_MAX:
        raise _opens(
            f"The {member} of the file is larger than {JSON_MAX // MB} MB, more than any model "
            "CandleStack takes. Upload a smaller model."
        )
    try:
        document = json.loads(archive.read(member))
    except (ValueError, RecursionError):  # not JSON, not UTF-8, or nested beyond reason
        document = None
    if not isinstance(document, dict):
        raise _opens(f"The {member} of the file is not valid JSON. " + _SAVE_AGAIN)
    return document


def _keras_version(metadata: dict[str, Any]) -> str:
    version = metadata.get("keras_version")
    if not isinstance(version, str) or not version or len(version) > _KERAS_VERSION_MAX:
        raise _opens(
            "The file does not say which Keras version saved it. Save the model again with "
            'Keras 3 (model.save("model.keras")) and upload that file.'
        )
    return version


def _is_keras_module(module: object) -> bool:
    return isinstance(module, str) and (module == "keras" or module.startswith("keras."))


def _check_architecture(config: dict[str, Any]) -> None:
    """Fails unless `config` is a Functional or Sequential Keras model without custom code."""
    if (
        config.get("class_name") not in _MODEL_CLASSES
        or not _is_keras_module(config.get("module"))
        or not isinstance(config.get("config"), dict)
    ):
        raise _opens(
            "The file holds no Functional or Sequential Keras model. A model of your own class "
            "cannot be checked without running its code. Build the model with keras.Model "
            "(inputs, outputs) or keras.Sequential and upload it again."
        )
    if (detail := _custom_code(config)) is not None:
        raise _opens(detail)


def _custom_code(config: dict[str, Any]) -> str | None:
    """What tells the user about the first custom code in the architecture, None without any.

    Walks the JSON with a stack of its own: a deeply nested file cannot exhaust Python's.
    """
    stack: list[tuple[Any, str | None]] = [(config, None)]
    while stack:
        node, layer = stack.pop()
        if isinstance(node, list):
            stack.extend((item, layer) for item in reversed(node))
        elif isinstance(node, dict):
            if (code := _code_of(node)) is not None:
                where = f'The layer "{layer}"' if layer else "The model"
                return (
                    f"{where} uses custom code ({code}), which CandleStack does not run. "
                    "Rebuild the model with the built-in Keras layers only and upload it again."
                )
            for key, value in reversed(node.items()):
                if key == _TRAINING_ONLY or key.endswith(_TRAINING_ONLY_SUFFIXES):
                    continue
                if key == "layers" and isinstance(value, list):
                    stack.extend((item, _shown(_layer_name(item)) or layer) for item in value[::-1])
                else:
                    stack.append((value, layer))
    return None


def _code_of(node: dict[str, Any]) -> str | None:
    """The class of a serialized object that is code rather than Keras' own configuration
    (a lambda, a class of another package or one the user registered); None for Keras' own."""
    class_name = node.get("class_name")
    if class_name is None:
        return None
    module = node.get("module")
    registered = node.get("registered_name")
    if (
        class_name in _CODE_LAYERS
        or (module is not None and not _is_keras_module(module))
        or (registered is not None and registered != class_name)
    ):
        return _shown(class_name) or "an object without a name"
    return None


def _shown(value: object) -> str | None:
    """`value` as a detail may show it: a string without control characters, cut short."""
    if not isinstance(value, str):
        return None
    return _CONTROL.sub("", value).strip()[:_SHOWN_MAX] or None


def _layer_name(layer: object) -> object:
    """The name of a serialized layer: on the layer in Keras 3, in its config before."""
    if not isinstance(layer, dict):
        return None
    if "name" in layer:
        return layer["name"]
    config = layer.get("config")
    return config.get("name") if isinstance(config, dict) else None


def count_parameters(weights: Path) -> int:
    """The number of weights of the layers in the HDF5 file `weights`: the sizes of the
    datasets under ``layers``, not ``optimizer`` (the optimizer's state). Reads the
    metadata of the datasets, never their data.

    Raises:
        ModelCheckFailed: The file cannot be read as HDF5, or holds no weights.
    """
    sizes: list[int] = []

    def add(_name: str, item: object) -> None:
        if isinstance(item, h5py.Dataset):
            sizes.append(item.size)

    try:
        with h5py.File(weights, "r") as file:
            group = file.get("layers")
            if isinstance(group, h5py.Group):
                group.visititems(add)
    except _HDF5_ERRORS as error:
        raise _weights(
            f"The weights of the model ({WEIGHTS}) cannot be read. " + _SAVE_AGAIN
        ) from error
    parameters = sum(sizes)
    if parameters == 0:
        raise _weights(_NO_WEIGHTS)
    if parameters > _PARAMETERS_MAX:
        raise _weights(f"The weights of the model ({WEIGHTS}) cannot be read. " + _SAVE_AGAIN)
    return parameters


def _layers(config: dict[str, Any]) -> list[dict[str, Any]]:
    """The model's own layers (not those of models nested in it)."""
    layers = config["config"].get("layers")
    if not isinstance(layers, list):
        return []
    return [layer for layer in layers if isinstance(layer, dict)]


def _sample_shape(shape: object) -> list[int] | None:
    """A shape with its batch dimension first, without it; None unless every other dimension
    is a known size."""
    if not isinstance(shape, list) or len(shape) < 2:
        return None
    dims = shape[1:]
    if all(isinstance(dim, int) and not isinstance(dim, bool) and dim > 0 for dim in dims):
        return dims
    return None


def _input_shape(layers: list[dict[str, Any]]) -> list[int] | None:
    """The shape of one input sample, when the model has exactly one input."""
    inputs = [layer for layer in layers if layer.get("class_name") == "InputLayer"]
    if len(inputs) != 1 or not isinstance(config := inputs[0].get("config"), dict):
        return None
    return _sample_shape(config.get("batch_shape", config.get("batch_input_shape")))


def _output_layer(config: dict[str, Any], layers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The layer that makes the model's one output: a Sequential's last, a Functional's
    ``output_layers`` when it names one layer."""
    if config["class_name"] == "Sequential":
        last = layers[-1] if layers else None
        return last if last is not None and last.get("class_name") != "InputLayer" else None
    outputs = config["config"].get("output_layers")
    # One output is [layer, node, tensor], or a list of just that; more are a longer list.
    if isinstance(outputs, list) and len(outputs) == 1:
        outputs = outputs[0]
    if not isinstance(outputs, list) or len(outputs) != 3 or not isinstance(outputs[0], str):
        return None
    named = [layer for layer in layers if _layer_name(layer) == outputs[0]]
    return named[0] if len(named) == 1 else None


def _output_shape(config: dict[str, Any], layers: list[dict[str, Any]]) -> list[int] | None:
    """The shape of one output, from the input shape the output layer was built with; None
    for a layer whose output shape is not plain from it."""
    layer = _output_layer(config, layers)
    build = layer.get("build_config") if layer is not None else None
    shape = _sample_shape(build.get("input_shape")) if isinstance(build, dict) else None
    if layer is None or shape is None:
        return None
    kind = layer.get("class_name")
    if kind == "Dense":
        settings = layer.get("config")
        units = settings.get("units") if isinstance(settings, dict) else None
        if isinstance(units, int) and not isinstance(units, bool) and units > 0:
            return [*shape[:-1], units]
        return None
    if kind == "Flatten":
        return [math.prod(shape)]
    return shape if kind in _SHAPE_KEEPING else None
