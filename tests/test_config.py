import os
from unittest.mock import patch, mock_open

import pytest
import yaml

from lambda_packer.config import Config


@pytest.fixture
def config_file_path(tmp_path):
    return tmp_path / "package_config.yaml"


@pytest.fixture
def config_instance(config_file_path):
    return Config(config_file_path)


@pytest.fixture
def create_valid_config(tmpdir):
    """Create a valid package_config.yaml file."""
    config_data = {
        "lambdas": {
            "lambda_example": {"type": ["zip"], "runtime": "3.8", "layers": ["common"]},
            "lambda_docker": {"type": ["docker"], "runtime": "3.9"},
        }
    }
    config_path = os.path.join(tmpdir, "package_config.yaml")
    with open(config_path, "w") as config_file:
        yaml.dump(config_data, config_file)
    return config_path


@pytest.fixture
def create_invalid_config(tmpdir):
    """Create an invalid package_config.yaml file missing required fields."""
    config_data = {
        "lambdas": {
            "lambda_example": {"layers": "common"}  # Invalid: layers should be a list
        }
    }
    config_path = os.path.join(tmpdir, "package_config.yaml")
    with open(config_path, "w") as config_file:
        yaml.dump(config_data, config_file)
    return config_path


def test_load_invalid_config(create_invalid_config):
    """Test loading the configuration from an invalid config file."""
    config = Config(create_invalid_config)

    with pytest.raises(ValueError, match="Config validation failed"):
        config.validate()


def test_validate_config(create_valid_config):
    """Test the validate method with a valid config."""
    config = Config(create_valid_config)
    config.validate()  # This should not raise an exception

    # Check that no errors occurred during validation
    assert config.errors == []


def test_missing_lambdas_section(tmpdir):
    """Test config validation when the 'lambdas' section is missing."""
    config_data = {}
    config_path = os.path.join(tmpdir, "package_config.yaml")
    with open(config_path, "w") as config_file:
        yaml.dump(config_data, config_file)

    config = Config(config_path)
    with pytest.raises(ValueError, match="Missing or empty 'lambdas' section"):
        config.validate()


@pytest.mark.parametrize(
    "config_content, expected",
    [
        (
            "lambdas:\n  lambda1:\n    type: zip\n",
            {"lambdas": {"lambda1": {"type": "zip"}}},
        ),
        ("", {}),
    ],
    ids=["valid_config", "empty_config"],
)
def test_load_config(config_instance, config_content, expected):
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch("os.path.exists", return_value=True):
            result = config_instance.load_config()

    assert result == expected


@pytest.mark.parametrize(
    "config_content, expected_error",
    [
        ("invalid_yaml: [unclosed", "Error parsing YAML config:"),
    ],
    ids=["invalid_yaml"],
)
def test_load_config_invalid_yaml(config_instance, config_content, expected_error):
    # Arrange
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch("os.path.exists", return_value=True):
            # Act & Assert
            with pytest.raises(ValueError, match=expected_error):
                config_instance.load_config()


@pytest.mark.parametrize(
    "config_data, expected_error",
    [
        ({}, "Missing or empty 'lambdas' section in config."),
        ({"lambdas": {"lambda1": {"type": ["docker"]}}}, None),
    ],
    ids=["missing_lambdas", "valid_config"],
)
def test_validate(config_instance, config_data, expected_error):
    # Arrange
    config_instance.config_data = config_data

    # Act & Assert
    if expected_error:
        with pytest.raises(ValueError, match=expected_error):
            config_instance.validate()
    else:
        config_instance.validate()
        assert not config_instance.errors


@pytest.mark.parametrize(
    "runtime, expected_error",
    [
        ("3.8", None),
        ("3.12", None),
        (
            "3.7",
            "Invalid runtime: 3.7. Supported runtimes are: 3.8, 3.9, 3.10, 3.11, 3.12",
        ),
    ],
    ids=["valid_runtime_3.8", "valid_runtime_3.12", "invalid_runtime"],
)
def test_validate_runtime(config_instance, runtime, expected_error):
    # Act
    config_instance.validate_runtime(runtime)

    # Assert
    if expected_error:
        assert expected_error in config_instance.errors
    else:
        assert not config_instance.errors


@pytest.mark.parametrize(
    "repo, lambda_name, layers, runtime, lambda_type, expected_output",
    [
        (
            "/repo",
            "lambda1",
            ["layer1"],
            "3.8",
            "zip",
            "Lambda 'lambda1' has been added to package_config.yaml.",
        ),
        (
            "/repo",
            "lambda1",
            ["layer1"],
            "3.8",
            "docker",
            "Lambda 'lambda1' has been added to package_config.yaml.",
        ),
    ],
    ids=["zip_lambda", "docker_lambda"],
)
def test_config_lambda(
    config_instance, repo, lambda_name, layers, runtime, lambda_type, expected_output
):
    # Arrange
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open()):
            with patch("click.secho") as mock_secho:
                # Act
                config_instance.config_lambda(
                    lambda_name,
                    layers,
                    runtime,
                    lambda_type,
                )

                # Assert
                mock_secho.assert_called_once_with(expected_output, fg="green")


@pytest.mark.parametrize(
    "layers, expected_lambdas",
    [
        (
            ["layer1"],
            {"lambda1": {"type": "zip", "runtime": "3.12", "layers": ["layer1"]}},
        ),
    ],
    ids=["single_lambda"],
)
def test_config_repo(config_instance, layers, expected_lambdas):
    # Arrange
    with patch("os.walk", return_value=[("/repo/lambda1", [], ["lambda_handler.py"])]):
        with patch("builtins.open", mock_open()):
            # Act
            config_instance.config_repo(layers)

            # Assert
            assert config_instance.config_data["lambdas"] == expected_lambdas


@pytest.mark.parametrize(
    "config_data, expected_lambdas",
    [
        ({"lambdas": {"lambda1": {"type": "zip"}}}, {"lambda1": {"type": "zip"}}),
        ({}, {}),
    ],
    ids=["existing_lambdas", "no_lambdas"],
)
def test_get_lambdas(config_instance, config_data, expected_lambdas):
    # Arrange
    config_instance.config_data = config_data

    # Act
    result = config_instance.get_lambdas()

    # Assert
    assert result == expected_lambdas


@pytest.mark.parametrize(
    "config_data, lambda_name, expected_config",
    [
        ({"lambdas": {"lambda1": {"type": "zip"}}}, "lambda1", {"type": "zip"}),
        ({"lambdas": {}}, "lambda1", None),
    ],
    ids=["existing_lambda", "non_existing_lambda"],
)
def test_get_lambda_config(config_instance, config_data, lambda_name, expected_config):
    # Arrange
    config_instance.config_data = config_data

    # Act
    result = config_instance.get_lambda_config(lambda_name)

    # Assert
    assert result == expected_config


@pytest.mark.parametrize(
    "config_data, lambda_name, expected_layers",
    [
        ({"lambdas": {"lambda1": {"layers": ["layer1"]}}}, "lambda1", ["layer1"]),
        ({"lambdas": {"lambda1": {}}}, "lambda1", []),
    ],
    ids=["existing_layers", "no_layers"],
)
def test_get_lambda_layers(config_instance, config_data, lambda_name, expected_layers):
    # Arrange
    config_instance.config_data = config_data

    # Act
    result = config_instance.get_lambda_layers(lambda_name)

    # Assert
    assert result == expected_layers


@pytest.mark.parametrize(
    "config_data, lambda_name, expected_runtime",
    [
        ({"lambdas": {"lambda1": {"runtime": "3.8"}}}, "lambda1", "3.8"),
        ({"lambdas": {"lambda1": {}}}, "lambda1", "3.12"),
    ],
    ids=["existing_runtime", "default_runtime"],
)
def test_get_lambda_runtime(
    config_instance, config_data, lambda_name, expected_runtime
):
    # Arrange
    config_instance.config_data = config_data

    # Act
    result = config_instance.get_lambda_runtime(lambda_name)

    # Assert
    assert result == expected_runtime


def test_config_repo_exclude_dirs(config_instance):
    exclude_dirs = ["exclude_this_dir"]
    layers = []

    with patch("os.walk") as mock_walk, patch.object(
        config_instance, "save_config"
    ) as mock_save:
        mock_walk.return_value = [
            ("/repo/exclude_this_dir", [], ["lambda_handler.py"]),
            ("/repo/include_this_dir", [], ["lambda_handler.py"]),
        ]

        config_instance.config_repo(layers, exclude_dirs)

        lambdas = config_instance.config_data["lambdas"]
        assert "exclude_this_dir" not in lambdas
        assert "include_this_dir" in lambdas
        mock_save.assert_called_once()


def test_config_repo_exclude_layers(config_instance):
    exclude_dirs = []
    layers = ["layer_to_exclude"]

    with patch("os.walk") as mock_walk, patch.object(
        config_instance, "save_config"
    ) as mock_save:
        mock_walk.return_value = [
            ("/repo/layer_to_exclude", [], ["lambda_handler.py"]),
            ("/repo/include_this_dir", [], ["lambda_handler.py"]),
        ]

        config_instance.config_repo(layers, exclude_dirs)

        lambdas = config_instance.config_data["lambdas"]
        assert "layer_to_exclude" not in lambdas
        assert "include_this_dir" in lambdas
        mock_save.assert_called_once()


@pytest.mark.parametrize(
    "platform, expected_error",
    [
        (["linux/x86_64"], None),
        (["linux/arm64"], None),
        (
            "invalid_platform",
            [
                f"Invalid platforms: invalid_platform. Supported platforms are: {', '.join(Config.valid_platforms)}"
            ],
        ),
    ],
    ids=["valid_platform_x86_64", "valid_platform_arm64", "invalid_platform"],
)
def test_validate_platforms(config_instance, platform, expected_error):
    config_instance.validate_platforms(platform)
    if expected_error:
        # assert the expected error list is in the list of errors
        assert all(error in config_instance.errors for error in expected_error)
    else:
        assert not config_instance.errors
