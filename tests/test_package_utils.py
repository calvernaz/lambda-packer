import subprocess
from unittest import mock

import pytest

from lambda_packer.package_utils import package_layer_internal


@pytest.fixture
def mock_os_functions():
    with mock.patch("os.path.exists") as mock_exists, mock.patch(
        "os.makedirs"
    ) as mock_makedirs, mock.patch("shutil.rmtree") as mock_rmtree, mock.patch(
        "shutil.copytree"
    ) as mock_copytree, mock.patch(
        "shutil.make_archive"
    ) as mock_make_archive, mock.patch(
        "subprocess.check_call"
    ) as mock_check_call, mock.patch(
        "click.echo"
    ) as mock_echo, mock.patch(
        "click.secho"
    ) as mock_secho:
        yield {
            "mock_exists": mock_exists,
            "mock_makedirs": mock_makedirs,
            "mock_rmtree": mock_rmtree,
            "mock_copytree": mock_copytree,
            "mock_make_archive": mock_make_archive,
            "mock_check_call": mock_check_call,
            "mock_echo": mock_echo,
            "mock_secho": mock_secho,
        }


@pytest.mark.parametrize(
    "layer_name, runtime, exists_side_effect, expected_echo, expected_secho",
    [
        (
            "test_layer",
            "3.8",
            [False, True, False],
            "Installing dependencies from test_layer/requirements.txt...",
            "Lambda layer test_layer packaged as dist/test_layer.zip.",
        ),
        (
            "empty_layer",
            "3.9",
            [False, False, False],
            None,
            "Lambda layer empty_layer packaged as dist/empty_layer.zip.",
        ),
        (
            "existing_layer",
            "3.7",
            [True, True, False],
            "Installing dependencies from existing_layer/requirements.txt...",
            "Lambda layer existing_layer packaged as dist/existing_layer.zip.",
        ),
    ],
    ids=[
        "happy_path_with_requirements",
        "happy_path_no_requirements",
        "happy_path_existing_temp",
    ],
)
def test_package_layer_internal_happy_path(
    layer_name,
    runtime,
    exists_side_effect,
    expected_echo,
    expected_secho,
    mock_os_functions,
):
    # Arrange
    mock_os_functions["mock_exists"].side_effect = exists_side_effect

    # Act
    package_layer_internal(layer_name, runtime)

    # Assert
    if expected_echo:
        mock_os_functions["mock_echo"].assert_called_once_with(expected_echo)
    mock_os_functions["mock_secho"].assert_called_once_with(expected_secho, fg="green")


@pytest.mark.parametrize(
    "layer_name, runtime, exists_side_effect, expected_exception",
    [
        (
            "test_layer",
            "3.8",
            [False, True, False],
            subprocess.CalledProcessError(1, "pip install"),
        ),
        ("empty_layer", "3.9", [False, False, False], None),
        (
            "existing_layer",
            "3.7",
            [True, True, False],
            subprocess.CalledProcessError(1, "pip install"),
        ),
    ],
    ids=[
        "error_during_pip_install",
        "no_requirements_no_error",
        "error_during_pip_install_existing_temp",
    ],
)
def test_package_layer_internal_error_cases(
    layer_name, runtime, exists_side_effect, expected_exception, mock_os_functions
):
    # Arrange
    mock_os_functions["mock_exists"].side_effect = exists_side_effect
    if expected_exception:
        mock_os_functions["mock_check_call"].side_effect = expected_exception

    # Act
    if expected_exception:
        with pytest.raises(subprocess.CalledProcessError):
            package_layer_internal(layer_name, runtime)
    else:
        package_layer_internal(layer_name, runtime)

    # Assert
    if not expected_exception:
        mock_os_functions["mock_secho"].assert_called_once()
