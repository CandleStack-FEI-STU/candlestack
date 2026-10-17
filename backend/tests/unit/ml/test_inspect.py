"""The static check of uploaded Keras files, on the real files of tests/fixtures/keras and on
broken ones made from them."""

import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import h5py
import pytest

from candlestack.ml import inspect
from candlestack.ml.errors import ModelCheckFailed
from candlestack.ml.inspect import ModelFacts, count_parameters, inspect_keras
from candlestack.ml.schemas import ModelCheck

FIXTURES = Path(__file__).parents[2] / "fixtures" / "keras"
SAVE_AGAIN = 'Save the model again with model.save("model.keras") and upload that file.'

Config = dict[str, Any]


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    return tmp_path / "weights.part"


def fixture(name: str) -> Path:
    return FIXTURES / f"{name}.keras"


def members(source: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(source) as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def write_zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def rezip(
    tmp_path: Path,
    source: str = "functional",
    *,
    drop: tuple[str, ...] = (),
    put: dict[str, bytes] | None = None,
) -> Path:
    """A copy of a fixture without the members `drop`, with the members `put` added or
    replaced."""
    files = {name: data for name, data in members(fixture(source)).items() if name not in drop}
    files.update(put or {})
    return write_zip(tmp_path / "model.keras", files)


def with_config(tmp_path: Path, edit: Callable[[Config], object], source: str = "functional"):
    """A copy of a fixture whose config.json `edit` changed in place."""
    config = json.loads(members(fixture(source))["config.json"])
    edit(config)
    return rezip(tmp_path, source, put={"config.json": json.dumps(config).encode()})


def layer(config: Config, name: str) -> Config:
    return next(item for item in config["config"]["layers"] if item["name"] == name)


def failure(path: Path, scratch: Path) -> ModelCheckFailed:
    with pytest.raises(ModelCheckFailed) as failed:
        inspect_keras(path, scratch)
    return failed.value


def opens_fails(path: Path, scratch: Path) -> str:
    """The detail of the failed `opens` check."""
    failed = failure(path, scratch)
    assert failed.check is ModelCheck.opens
    assert ";" not in failed.detail
    return failed.detail


@pytest.mark.parametrize(
    ("name", "facts"),
    [
        ("functional", ModelFacts("3.15.1", 9325, [25, 23], [1])),
        ("sequential", ModelFacts("3.15.1", 1235, [30, 5], [3])),
        # A user's regularizer and metric only shape and report training.
        ("custom_regularizer", ModelFacts("3.15.1", 4617, [25, 23], [1])),
        ("two_inputs", ModelFacts("3.15.1", 586, None, [1])),
    ],
)
def test_real_models_pass(name: str, facts: ModelFacts, scratch: Path) -> None:
    assert inspect_keras(fixture(name), scratch) == facts


@pytest.mark.parametrize(
    ("name", "detail"),
    [
        ("lambda_layer", 'The layer "lambda" uses custom code (Lambda)'),
        ("custom_layer", 'The layer "scale" uses custom code (Scale)'),
    ],
)
def test_custom_code_fails_opens(name: str, detail: str, scratch: Path) -> None:
    assert opens_fails(fixture(name), scratch) == (
        f"{detail}, which CandleStack does not run. Rebuild the model with the built-in Keras "
        "layers only and upload it again."
    )


def test_a_model_without_weights_fails_weights(scratch: Path) -> None:
    failed = failure(fixture("no_weights"), scratch)

    assert failed.check is ModelCheck.weights
    assert failed.detail == (
        "The file holds the layers only. Save the model after training and upload that file."
    )


@pytest.mark.parametrize(
    "content",
    [b"", b"not a zip at all", fixture("functional").read_bytes()[:70_000]],
    ids=["empty", "not-a-zip", "truncated"],
)
def test_a_file_that_is_no_zip_fails_opens(content: bytes, tmp_path: Path, scratch: Path):
    path = tmp_path / "model.keras"
    path.write_bytes(content)

    assert opens_fails(path, scratch) == (
        "The file is not a readable Keras model. It may be damaged or not a .keras file at all. "
        + SAVE_AGAIN
    )


def test_a_damaged_member_fails_opens(tmp_path: Path, scratch: Path) -> None:
    content = bytearray(fixture("functional").read_bytes())
    content[80_000] ^= 0xFF  # inside the stored weights, so their CRC does not match
    path = tmp_path / "model.keras"
    path.write_bytes(bytes(content))

    assert opens_fails(path, scratch).startswith("The file is not a readable Keras model.")


@pytest.mark.parametrize(
    "member", ["../config.py", "assets/../../evil.sh", "/etc/passwd", "\\evil.dll", "C:/evil"]
)
def test_a_path_outside_the_model_fails_opens(member: str, tmp_path: Path, scratch: Path):
    path = rezip(tmp_path, put={member: b"x"})

    assert opens_fails(path, scratch) == (
        "The file holds a path that points outside the model. " + SAVE_AGAIN
    )


def test_an_unknown_member_fails_opens(tmp_path: Path, scratch: Path) -> None:
    path = rezip(tmp_path, put={"custom_objects.py": b"import os"})

    assert opens_fails(path, scratch) == (
        "The file holds files a Keras model does not have. " + SAVE_AGAIN
    )


def test_assets_are_fine(tmp_path: Path, scratch: Path) -> None:
    path = rezip(tmp_path, put={"assets/": b"", "assets/vocabulary.txt": b"up\ndown\n"})

    assert inspect_keras(path, scratch).parameters == 9325


@pytest.mark.parametrize("member", ["config.json", "metadata.json", "model.weights.h5"])
def test_a_missing_member_fails_opens(member: str, tmp_path: Path, scratch: Path) -> None:
    path = rezip(tmp_path, drop=(member,))

    assert opens_fails(path, scratch) == (
        f"The file has no {member}, so it is not a whole Keras model. " + SAVE_AGAIN
    )


def test_a_zip_bomb_fails_opens(
    tmp_path: Path, scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fixture unpacks to 145 KB: a limit of 100 KB stands for 200 MB.
    monkeypatch.setattr(inspect, "UNPACKED_MAX", 100_000)

    assert opens_fails(fixture("functional"), scratch) == (
        "The file unpacks to more than 0 MB, more than any model CandleStack takes. "
        "Upload a smaller model."
    )
    assert not scratch.exists()  # nothing was unpacked


def test_the_real_zip_bomb_limit_is_four_files() -> None:
    assert inspect.UNPACKED_MAX == 200 * 1024 * 1024
    assert inspect.JSON_MAX == 5 * 1024 * 1024


def test_a_huge_config_fails_opens(
    tmp_path: Path, scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(inspect, "JSON_MAX", 5_000)  # the config is 5540 bytes

    assert opens_fails(fixture("functional"), scratch).startswith(
        "The config.json of the file is larger than 0 MB"
    )


@pytest.mark.parametrize(
    "content",
    [b"{", b"[1, 2]", b"\xff\xfe{}", b"[" * 100_000 + b"]" * 100_000],
    ids=["broken", "a-list", "not-utf8", "nested-too-deep"],
)
@pytest.mark.parametrize("member", ["config.json", "metadata.json"])
def test_json_that_is_no_object_fails_opens(
    member: str, content: bytes, tmp_path: Path, scratch: Path
) -> None:
    path = rezip(tmp_path, put={member: content})

    assert (
        opens_fails(path, scratch) == f"The {member} of the file is not valid JSON. " + SAVE_AGAIN
    )


@pytest.mark.parametrize(
    "metadata", [{}, {"keras_version": ""}, {"keras_version": 3}, {"keras_version": "3." * 20}]
)
def test_metadata_without_a_keras_version_fails_opens(
    metadata: dict[str, Any], tmp_path: Path, scratch: Path
) -> None:
    path = rezip(tmp_path, put={"metadata.json": json.dumps(metadata).encode()})

    assert opens_fails(path, scratch).startswith(
        "The file does not say which Keras version saved it."
    )


def _subclassed(config: Config) -> None:
    config.update(class_name="TradingModel", module="my_models", registered_name="Custom>X")


@pytest.mark.parametrize(
    "edit",
    [
        _subclassed,
        lambda config: config.update(module="kerasx.models"),
        lambda config: config.update(module=None),
        lambda config: config.update(config=[]),
        lambda config: config.update(class_name="Model"),
    ],
    ids=["subclassed", "not-keras", "no-module", "no-config", "plain-model"],
)
def test_anything_but_a_functional_or_sequential_model_fails_opens(
    edit: Callable[[Config], None], tmp_path: Path, scratch: Path
) -> None:
    path = with_config(tmp_path, edit)

    assert opens_fails(path, scratch).startswith(
        "The file holds no Functional or Sequential Keras model."
    )


def _from_package(config: Config) -> None:
    layer(config, "dense")["module"] = "my_package.layers"


def _registered_initializer(config: Config) -> None:
    layer(config, "dense")["config"]["kernel_initializer"]["registered_name"] = "Custom>Init"


def _tf_op(config: Config) -> None:
    layer(config, "flatten")["class_name"] = "TFOpLambda"


def _keras2_layer(config: Config) -> None:
    dense = layer(config, "dense")
    del dense["name"]  # Keras 2 names a layer in its config only
    dense["module"] = "evil"


@pytest.mark.parametrize(
    ("edit", "detail"),
    [
        (_from_package, 'The layer "dense" uses custom code (Dense)'),
        (_registered_initializer, 'The layer "dense" uses custom code (GlorotUniform)'),
        (_tf_op, 'The layer "flatten" uses custom code (TFOpLambda)'),
        (_keras2_layer, 'The layer "dense" uses custom code (Dense)'),
    ],
    ids=["another-package", "registered", "tf-op", "keras-2-layer"],
)
def test_custom_code_in_a_layer_fails_opens(
    edit: Callable[[Config], None], detail: str, tmp_path: Path, scratch: Path
) -> None:
    assert opens_fails(with_config(tmp_path, edit), scratch).startswith(detail + ", which")


def test_custom_code_outside_the_layers_names_the_model(tmp_path: Path, scratch: Path) -> None:
    def edit(config: Config) -> None:
        config["config"]["dtype"] = {"class_name": "\x00Policy\n", "module": "evil", "config": {}}

    assert opens_fails(with_config(tmp_path, edit), scratch).startswith(
        "The model uses custom code (Policy), which"
    )


@pytest.mark.parametrize("class_name", ["\n", 5])
def test_an_object_without_a_shown_name(class_name: object, tmp_path: Path, scratch: Path):
    def edit(config: Config) -> None:
        dense = layer(config, "dense")
        dense.update(name="\x07", class_name=class_name, module="evil")

    assert opens_fails(with_config(tmp_path, edit), scratch).startswith(
        "The model uses custom code (an object without a name), which"
    )


def test_what_only_shapes_or_reports_training_is_ignored(tmp_path: Path, scratch: Path) -> None:
    custom = {"module": None, "class_name": "Mine", "registered_name": "Custom>Mine"}

    def edit(config: Config) -> None:
        dense = layer(config, "dense")["config"]
        dense["kernel_regularizer"] = custom
        dense["bias_constraint"] = custom
        config["compile_config"]["loss"] = custom

    assert inspect_keras(with_config(tmp_path, edit), scratch).parameters == 9325


def test_weights_that_are_no_hdf5_fail_weights(tmp_path: Path, scratch: Path) -> None:
    path = rezip(tmp_path, put={"model.weights.h5": b"not HDF5"})

    failed = failure(path, scratch)

    assert failed.check is ModelCheck.weights
    assert failed.detail == "The weights of the model (model.weights.h5) cannot be read. " + (
        SAVE_AGAIN
    )


def test_only_the_layers_count_not_the_optimizer(tmp_path: Path) -> None:
    weights = tmp_path / "model.weights.h5"
    with h5py.File(weights, "w") as file:
        file.create_dataset("optimizer/vars/0", data=[1.0, 2.0])
        file.create_group("layers")

    with pytest.raises(ModelCheckFailed) as failed:
        count_parameters(weights)

    assert failed.value.check is ModelCheck.weights
    assert failed.value.detail.startswith("The file holds the layers only.")


def test_weights_without_a_layers_group(tmp_path: Path) -> None:
    weights = tmp_path / "model.weights.h5"
    with h5py.File(weights, "w") as file:
        file.create_dataset("layers", data=[1.0])  # a dataset, not the group of the layers

    with pytest.raises(ModelCheckFailed):
        count_parameters(weights)


def test_more_weights_than_postgres_counts_fail_weights(tmp_path: Path) -> None:
    weights = tmp_path / "model.weights.h5"
    with h5py.File(weights, "w") as file:
        # Chunked and never written: the shape is metadata only, nothing is allocated.
        file.create_dataset("layers/dense/vars/0", shape=(2**62, 4), dtype="i1", chunks=(1, 4))

    with pytest.raises(ModelCheckFailed) as failed:
        count_parameters(weights)

    assert failed.value.detail.startswith("The weights of the model (model.weights.h5) cannot")


def _output(name: object) -> Callable[[Config], None]:
    def edit(config: Config) -> None:
        config["config"]["output_layers"] = name

    return edit


@pytest.mark.parametrize(
    ("edit", "shape"),
    [
        (_output(["flatten", 0, 0]), [575]),
        (_output(["batch_normalization", 0, 0]), [25, 23]),
        (_output([["dense_1", 0, 0]]), [1]),
        (_output(["dropout", 0, 0]), None),  # built without a build_config
        (_output(["input_layer", 0, 0]), None),  # no build_config either
        (_output([["dense", 0, 0], ["dense_1", 0, 0]]), None),  # two outputs
        (_output(["nowhere", 0, 0]), None),
        (_output("dense_1"), None),
    ],
    ids=[
        "flatten",
        "shape-keeping",
        "one-in-a-list",
        "no-build-config",
        "input-layer",
        "two-outputs",
        "unknown-layer",
        "malformed",
    ],
)
def test_the_output_shape(
    edit: Callable[[Config], None], shape: list[int] | None, tmp_path: Path, scratch: Path
) -> None:
    assert inspect_keras(with_config(tmp_path, edit), scratch).output_shape == shape


def _units(units: object) -> Callable[[Config], None]:
    def edit(config: Config) -> None:
        layer(config, "dense_1")["config"]["units"] = units

    return edit


def _variable_length(config: Config) -> None:
    layer(config, "dense_1")["build_config"]["input_shape"] = [None, None]


def _no_dense_config(config: Config) -> None:
    layer(config, "dense_1")["config"] = None
    layer(config, "dense_1")["name"] = "dense_1"


def _not_plain(config: Config) -> None:
    layer(config, "dense_1")["class_name"] = "Conv1D"


@pytest.mark.parametrize(
    ("edit", "shape"),
    [
        (_units(4), [4]),
        (_units(True), None),
        (_units(0), None),
        (_no_dense_config, None),
        (_variable_length, None),
        (_not_plain, None),
    ],
    ids=["units", "bool-units", "no-units", "no-config", "unknown-size", "not-plain"],
)
def test_the_output_shape_of_the_output_layer(
    edit: Callable[[Config], None], shape: list[int] | None, tmp_path: Path, scratch: Path
) -> None:
    assert inspect_keras(with_config(tmp_path, edit), scratch).output_shape == shape


def _batch_shape(shape: object, key: str = "batch_shape") -> Callable[[Config], None]:
    def edit(config: Config) -> None:
        settings = layer(config, "input_layer")["config"]
        del settings["batch_shape"]
        settings[key] = shape

    return edit


def _input_config(config: Config) -> None:
    layer(config, "input_layer")["config"] = "?"


@pytest.mark.parametrize(
    ("edit", "shape"),
    [
        (_batch_shape([None, 25, 23], "batch_input_shape"), [25, 23]),
        (_batch_shape([None, None, 23]), None),
        (_batch_shape([None]), None),
        (_batch_shape("25x23"), None),
        (_input_config, None),
    ],
    ids=["keras-2", "unknown-size", "no-dimension", "malformed", "no-config"],
)
def test_the_input_shape(
    edit: Callable[[Config], None], shape: list[int] | None, tmp_path: Path, scratch: Path
) -> None:
    assert inspect_keras(with_config(tmp_path, edit), scratch).input_shape == shape


def test_a_sequential_of_an_input_only_has_no_output_shape(tmp_path: Path, scratch: Path):
    def edit(config: Config) -> None:
        config["config"]["layers"] = config["config"]["layers"][:1]

    facts = inspect_keras(with_config(tmp_path, edit, "sequential"), scratch)

    assert facts.input_shape == [30, 5]
    assert facts.output_shape is None


def test_a_model_without_a_list_of_layers_has_no_shapes(tmp_path: Path, scratch: Path) -> None:
    def edit(config: Config) -> None:
        config["config"]["layers"] = {"not": "a list"}

    facts = inspect_keras(with_config(tmp_path, edit, "sequential"), scratch)

    assert (facts.input_shape, facts.output_shape) == (None, None)


def test_what_is_no_layer_in_the_layers_is_passed_over(tmp_path: Path, scratch: Path) -> None:
    def edit(config: Config) -> None:
        config["config"]["layers"].insert(1, "not a layer")

    assert inspect_keras(with_config(tmp_path, edit), scratch).output_shape == [1]


def test_a_sequential_without_layers_has_no_output_shape(tmp_path: Path, scratch: Path) -> None:
    def edit(config: Config) -> None:
        config["config"]["layers"] = []

    assert inspect_keras(with_config(tmp_path, edit, "sequential"), scratch).output_shape is None
