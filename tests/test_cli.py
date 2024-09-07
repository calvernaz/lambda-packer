import os
import pytest
import yaml
from click.testing import CliRunner
from lambda_packer.cli import add_lambda, init, package, package_layer
from unittest.mock import patch, MagicMock


@pytest.fixture
def setup_test_directory(tmpdir):
    """Fixture to set up a temporary directory for testing."""
    os.chdir(tmpdir)
    yield tmpdir
    os.chdir("..")


def test_init_command(setup_test_directory):
    """Test the init command."""
    runner = CliRunner()
    result = runner.invoke(init, ["test_project", "--lambda-name", "lambda_example"])

    assert os.path.exists("test_project")
    assert os.path.exists("test_project/lambda_example")
    assert os.path.exists("test_project/package_config.yaml")
    assert result.exit_code == 0

    # Verify package_config.yaml content
    with open("test_project/package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_example" in config_data["lambdas"]
        assert config_data["lambdas"]["lambda_example"]["type"] == "zip"


def test_add_lambda_command(setup_test_directory):
    """Test the lambda command."""
    runner = CliRunner()
    runner.invoke(init, ["test_project", "--lambda-name", "lambda_example"])

    os.chdir("test_project")
    result = runner.invoke(
        add_lambda,
        [
            "lambda_docker",
            "--runtime",
            "3.9",
            "--type",
            "docker",
            "--layers",
            "common",
            "--layers",
            "shared",
        ],
    )

    assert os.path.exists("lambda_docker")

    # Verify package_config.yaml content
    with open("package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_docker" in config_data["lambdas"]
        assert config_data["lambdas"]["lambda_docker"]["runtime"] == "3.9"
        assert config_data["lambdas"]["lambda_docker"]["type"] == "docker"
        assert config_data["lambdas"]["lambda_docker"]["layers"] == ["common", "shared"]
    assert result.exit_code == 0


def test_package_zip_command(setup_test_directory):
    """Test packaging a lambda as a zip."""
    runner = CliRunner()

    # Initialize the project and add a zip-type lambda
    runner.invoke(init, ["test_project", "--lambda-name", "lambda_example"])
    os.chdir("test_project")

    runner.invoke(add_lambda, ["lambda_zip", "--runtime", "3.8", "--type", "zip"])

    # Simulate adding lambda handler and requirements.txt
    os.makedirs("lambda_zip", exist_ok=True)
    with open("lambda_zip/lambda_handler.py", "w") as f:
        f.write(
            'def lambda_handler(event, context):\n    return {"statusCode": 200, "body": "Hello"}'
        )

    result = runner.invoke(package, ["lambda_zip"])

    # Check that the lambda zip file is created in the dist directory
    assert os.path.exists("dist/lambda_zip.zip")

    # Verify package_config.yaml content
    with open("package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_zip" in config_data["lambdas"]
        assert config_data["lambdas"]["lambda_zip"]["runtime"] == "3.8"
        assert config_data["lambdas"]["lambda_zip"]["type"] == "zip"
    assert result.exit_code == 0


@patch("lambda_packer.cli.docker_from_env")
def test_package_docker_command(mock_docker, setup_test_directory):
    """Test packaging a lambda as a docker container."""
    # Mock the Docker client and the build process
    mock_client = MagicMock()
    mock_docker.return_value = mock_client
    mock_client.api.build.return_value = iter([{"stream": "Step 1/1 : DONE"}])

    runner = CliRunner()

    # Initialize the project and add a docker-type lambda
    runner.invoke(init, ["test_project", "--lambda-name", "lambda_example"])
    os.chdir("test_project")

    runner.invoke(add_lambda, ["lambda_docker", "--runtime", "3.9", "--type", "docker"])

    # Simulate adding lambda handler and requirements.txt
    os.makedirs("lambda_docker", exist_ok=True)
    with open("lambda_docker/lambda_handler.py", "w") as f:
        f.write(
            'def lambda_handler(event, context):\n    return {"statusCode": 200, "body": "Hello from Docker"}'
        )

    # Manually create a Dockerfile
    with open("lambda_docker/Dockerfile", "w") as dockerfile:
        dockerfile.write(
            f"""
        FROM public.ecr.aws/lambda/python:3.9
        WORKDIR /var/task
        COPY lambda_handler.py ./
        COPY requirements.txt ./
        RUN pip install --no-cache-dir -r requirements.txt
        CMD ["lambda_handler.lambda_handler"]
        """
        )

    # Now invoke the package command
    result = runner.invoke(package, ["lambda_docker"])

    # Check if Dockerfile exists and if the docker build was initiated
    assert os.path.exists("lambda_docker/Dockerfile")

    # Verify package_config.yaml content
    with open("package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_docker" in config_data["lambdas"]
        assert config_data["lambdas"]["lambda_docker"]["runtime"] == "3.9"
        assert config_data["lambdas"]["lambda_docker"]["type"] == "docker"
    assert result.exit_code == 0
