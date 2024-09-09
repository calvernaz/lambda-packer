import pytest
import os
import yaml
from lambda_packer.config import Config  # Assuming your config file is named config.py


@pytest.fixture
def create_valid_config(tmpdir):
    """Create a valid package_config.yaml file."""
    config_data = {
        "lambdas": {
            "lambda_example": {"type": "zip", "runtime": "3.8", "layers": ["common"]},
            "lambda_docker": {"type": "docker", "runtime": "3.9"},
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


def test_load_config(create_valid_config):
    """Test loading the configuration from a valid config file."""
    config = Config(create_valid_config)
    lambdas = config.get_lambdas()

    assert "lambda_example" in lambdas
    assert lambdas["lambda_example"]["type"] == "zip"
    assert lambdas["lambda_example"]["runtime"] == "3.8"
    assert lambdas["lambda_example"]["layers"] == ["common"]


def test_load_invalid_config(create_invalid_config):
    """Test loading the configuration from an invalid config file."""
    config = Config(create_invalid_config)

    with pytest.raises(ValueError, match="Config validation failed"):
        config.validate()


def test_validate_runtime(create_valid_config):
    """Test that the validate_runtime method correctly validates supported runtimes."""
    config = Config(create_valid_config)

    # This should pass as the runtime is valid
    config.validate_runtime("3.9")
    assert config.errors == []

    # Invalid runtime
    config.validate_runtime("3.5")
    assert any("Invalid runtime: 3.5" in error for error in config.errors)


def test_validate_config(create_valid_config):
    """Test the validate method with a valid config."""
    config = Config(create_valid_config)
    config.validate()  # This should not raise an exception

    # Check that no errors occurred during validation
    assert config.errors == []


def test_get_lambda_config(create_valid_config):
    """Test fetching a specific lambda config."""
    config = Config(create_valid_config)
    lambda_config = config.get_lambda_config("lambda_docker")

    assert lambda_config["type"] == "docker"
    assert lambda_config["runtime"] == "3.9"


def test_get_lambda_layers(create_valid_config):
    """Test fetching the layers associated with a specific lambda."""
    config = Config(create_valid_config)
    layers = config.get_lambda_layers("lambda_example")

    assert layers == ["common"]

    # Test a lambda with no layers
    layers = config.get_lambda_layers("lambda_docker")
    assert layers == []


def test_missing_lambdas_section(tmpdir):
    """Test config validation when the 'lambdas' section is missing."""
    config_data = {}
    config_path = os.path.join(tmpdir, "package_config.yaml")
    with open(config_path, "w") as config_file:
        yaml.dump(config_data, config_file)

    config = Config(config_path)
    with pytest.raises(ValueError, match="Missing or empty 'lambdas' section"):
        config.validate()


def test_validate_with_missing_type(tmpdir):
    """Test config validation when 'type' is missing from a lambda."""
    config_data = {"lambdas": {"lambda_example": {"runtime": "3.8"}}}
    config_path = os.path.join(tmpdir, "package_config.yaml")
    with open(config_path, "w") as config_file:
        yaml.dump(config_data, config_file)

    config = Config(config_path)

    with pytest.raises(ValueError, match="Missing 'type' for lambda"):
        config.validate()
