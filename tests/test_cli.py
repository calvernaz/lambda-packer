import os
from unittest.mock import patch, MagicMock

import pytest
import yaml
from click.testing import CliRunner

from lambda_packer.cli import add_lambda, init, package, main


@pytest.fixture
def setup_test_directory(tmpdir):
    """Fixture to set up a temporary monorepo directory for testing."""
    # Create temporary directories for lambdas
    lambda_dir = tmpdir.mkdir("lambda_a")
    lambda_b_dir = tmpdir.mkdir("lambda_b")

    # Add a lambda_handler.py file to simulate a Zip lambda
    lambda_dir.join("lambda_handler.py").write("def lambda_handler(event, context): return {'statusCode': 200}")

    # Add a Dockerfile to simulate a Docker lambda
    lambda_b_dir.join("Dockerfile").write("FROM python:3.8-slim")

    # Change working directory to the test monorepo
    os.chdir(tmpdir)
    return tmpdir

def test_clean_command_missing_package_config(tmpdir):
    """Test that clean command shows an error message when package_config.yaml is missing."""
    runner = CliRunner()

    # Change to a temporary directory (without package_config.yaml)
    with tmpdir.as_cwd():
        # Ensure no package_config.yaml exists
        assert not os.path.exists("package_config.yaml")

        # Run the clean command
        result = runner.invoke(main, ['clean'])

        # Verify the error message
        assert result.exit_code == 0  # Exit code should be 0 for successful command execution
        assert "Error: 'package_config.yaml' not found in the current directory." in result.output
        assert "Please make sure you're in the correct monorepo directory" in result.output


def test_add_lambda_to_config(setup_test_directory):
    """Test adding a specific lambda to an existing package_config.yaml."""
    runner = CliRunner()

    # First, simulate creating a partial package_config.yaml file
    initial_config = {
        "lambdas": {
            "lambda_a": {
                "type": "zip",
                "runtime": "3.8"
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(initial_config, config_file)

    # Run the lambda-packer config lambda lambda_b command
    result = runner.invoke(main, ['config', 'lambda_b'])

    # Verify that lambda_b has been added to the package_config.yaml
    with open("package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_b" in config_data["lambdas"]
        assert config_data["lambdas"]["lambda_b"]["type"] == "docker"
        assert config_data["lambdas"]["lambda_b"]["runtime"] == "3.8"

    # Verify the command output
    assert result.exit_code == 0
    assert "Lambda 'lambda_b' has been added to package_config.yaml." in result.output

def test_scan_entire_monorepo(setup_test_directory):
    """Test scanning the entire monorepo and generating package_config.yaml."""
    runner = CliRunner()

    # Run the lambda-packer config command to scan the whole monorepo
    result = runner.invoke(main, ['config'])

    # Verify that both lambda_a and lambda_b are included in package_config.yaml
    with open("package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_a" in config_data["lambdas"]
        assert config_data["lambdas"]["lambda_a"]["type"] == "zip"
        assert config_data["lambdas"]["lambda_b"]["type"] == "docker"

    # Verify the command output
    assert result.exit_code == 0
    assert "Updated package_config.yaml with 2 lambda(s)." in result.output

def test_skip_existing_lambda_in_config(setup_test_directory):
    """Test skipping a lambda that's already in package_config.yaml."""
    runner = CliRunner()

    # Create an initial package_config.yaml that includes lambda_a
    initial_config = {
        "lambdas": {
            "lambda_a": {
                "type": "zip",
                "runtime": "3.8"
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(initial_config, config_file)

    # Run the lambda-packer config lambda lambda_a command
    result = runner.invoke(main, ['config', 'lambda_a'])

    # Verify that the command skips adding lambda_a again
    with open("package_config.yaml", "r") as config_file:
        config_data = yaml.safe_load(config_file)
        assert "lambda_a" in config_data["lambdas"]  # It should still be there
        assert len(config_data["lambdas"]) == 1  # No duplicates should be added

    # Verify the command output
    assert result.exit_code == 0
    assert "Lambda 'lambda_a' is already included in package_config.yaml." in result.output


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
    """Test packaging a lambda as a Zip."""
    runner = CliRunner()

    # Simulate a Zip lambda in the directory
    lambda_path = os.path.join(setup_test_directory, "lambda_a")

    # Check if the directory exists before creating it
    if not os.path.exists(lambda_path):
        os.makedirs(lambda_path)

    with open(os.path.join(lambda_path, "lambda_handler.py"), "w") as f:
        f.write("def lambda_handler(event, context): return 'Hello'")

    # Create package_config.yaml with lambda_a
    package_config = {
        "lambdas": {
            "lambda_a": {
                "type": "zip",
                "runtime": "3.8"
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command
    result = runner.invoke(main, ['package', 'lambda_a'])

    # Assert that the output shows successful packaging
    assert result.exit_code == 0
    #assert "Packaging lambda 'lambda_a'" in result.output
    assert "Lambda lambda_a packaged" in result.output



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


def test_missing_package_config():
    """Test that a friendly error message is shown when package_config.yaml is missing."""
    runner = CliRunner()

    # Ensure the test directory does not have package_config.yaml
    if os.path.exists("package_config.yaml"):
        os.remove("package_config.yaml")

    # Run the lambda-packer package command, expecting it to fail with a friendly message
    result = runner.invoke(main, ['package', 'lambda_example'])

    # Check that the friendly error message is in the output
    assert "Error: The config file 'package_config.yaml' was not found" in result.output
    assert result.exit_code == 1

def test_package_specific_lambda(setup_test_directory):
    """Test packaging a specific lambda defined in package_config.yaml."""
    runner = CliRunner()

    # Simulate a Zip lambda
    lambda_path = os.path.join(setup_test_directory, "lambda_a")

    if not os.path.exists(lambda_path):
        os.makedirs(lambda_path)

    with open(os.path.join(lambda_path, "lambda_handler.py"), "w") as f:
        f.write("def lambda_handler(event, context): return 'Hello'")

    # Create package_config.yaml with lambda_a
    package_config = {
        "lambdas": {
            "lambda_a": {
                "type": "zip",
                "runtime": "3.8"
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command for lambda_a
    result = runner.invoke(main, ['package', 'lambda_a'])

    # Assert that lambda_a was packaged successfully
    assert result.exit_code == 0
    assert f"Lambda lambda_a packaged as" in result.output  # Match the actual output format


def test_package_all_lambdas(setup_test_directory):
    """Test packaging all lambdas defined in package_config.yaml."""
    runner = CliRunner()

    # Create a package_config.yaml with both lambda_a and lambda_b
    package_config = {
        "lambdas": {
            "lambda_a": {
                "type": "zip",
                "runtime": "3.8"
            },
            "lambda_b": {
                "type": "docker",
                "runtime": "3.9"
            }
        }
    }

    # Write the package_config.yaml in the root of the test directory
    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the lambda-packer package command (which should package all lambdas)
    result = runner.invoke(main, ['package'])

    # Assert that both lambda_a and lambda_b were packaged successfully
    assert result.exit_code == 0

    # Check the output contains success messages for both lambda_a and lambda_b
    assert "Packaging lambda 'lambda_a'" in result.output
    assert "Lambda lambda_a packaged" in result.output
    assert "Packaging lambda 'lambda_b'" in result.output
    assert "Successfully tagged lambda_b" in result.output

    # Optional: Verify that the expected zip and Docker image files were created
    assert os.path.exists(os.path.join("dist", "lambda_a.zip"))  # For lambda_a (Zip)
    # You can also check if the Docker image for lambda_b is created via the Docker client if needed.

    assert "Finished packaging all lambdas in package_config.yaml." in result.output

def test_package_docker_generates_templated_dockerfile(setup_test_directory):
    """Test that lambda-packer generates a Dockerfile using a template."""
    runner = CliRunner()

    # Simulate lambda_with_layer
    lambda_with_layer_path = os.path.join(setup_test_directory, "lambda_with_layer")
    if not os.path.exists(lambda_with_layer_path):
        os.makedirs(lambda_with_layer_path)

    # Simulate Lambda function code
    with open(os.path.join(lambda_with_layer_path, "lambda_handler.py"), "w") as f:
        f.write("def lambda_handler(event, context): return 'Hello from Lambda with Layer'")

    # Create package_config.yaml with one lambda that has a layer
    package_config = {
        "lambdas": {
            "lambda_with_layer": {
                "type": "docker",
                "runtime": "3.9",
                "layers": ["common"]
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command for the lambda
    result = runner.invoke(main, ['package', 'lambda_with_layer'], catch_exceptions=False)
    print(f"Command output:\n{result.output}")
    assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}"

    # Verify Dockerfile is created
    dockerfile_path = os.path.join(lambda_with_layer_path, "Dockerfile")
    assert os.path.exists(dockerfile_path), f"Dockerfile not found at {dockerfile_path}"

    # Check the content of the Dockerfile
    with open(dockerfile_path) as f:
        dockerfile_content = f.read()
    print(f"Dockerfile content:\n{dockerfile_content}")

    # Verify the Dockerfile includes the expected layer COPY command
    assert "COPY ./common" in dockerfile_content, "Layer copy command not found in Dockerfile"


def test_package_docker_generates_dockerfile_with_custom_layers(setup_test_directory):
    """Test that lambda-packer generates a Dockerfile with custom layers."""
    runner = CliRunner()

    # Simulate a Lambda with custom layer
    lambda_with_layer_path = os.path.join(setup_test_directory, "lambda_with_custom_layer")
    if not os.path.exists(lambda_with_layer_path):
        os.makedirs(lambda_with_layer_path)
    with open(os.path.join(lambda_with_layer_path, "lambda_handler.py"), "w") as f:
        f.write("def lambda_handler(event, context): return 'Hello from Lambda with Custom Layer'")

    # Create package_config.yaml with custom layer
    package_config = {
        "lambdas": {
            "lambda_with_custom_layer": {
                "type": "docker",
                "runtime": "3.9",
                "layers": ["layer_custom"]
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command
    result = runner.invoke(main, ['package', 'lambda_with_custom_layer'])
    assert os.path.exists(os.path.join(lambda_with_layer_path, "Dockerfile"))

    # Verify the Dockerfile contains the correct layer logic
    dockerfile_content = open(os.path.join(lambda_with_layer_path, "Dockerfile")).read()
    assert "COPY ./layer_custom" in dockerfile_content
    assert "RUN if [ -f '${LAMBDA_TASK_ROOT}/layer_custom/requirements.txt'" in dockerfile_content

def test_package_docker_deletes_generated_dockerfile(setup_test_directory):
    """Test that lambda-packer deletes the generated Dockerfile if --keep-dockerfile is not set."""
    runner = CliRunner()

    # Simulate a Lambda
    lambda_path = os.path.join(setup_test_directory, "lambda_a")
    if not os.path.exists(lambda_path):
        os.makedirs(lambda_path)
    with open(os.path.join(lambda_path, "lambda_handler.py"), "w") as f:
        f.write("def lambda_handler(event, context): return 'Hello from Lambda'")

    # Create package_config.yaml
    package_config = {
        "lambdas": {
            "lambda_a": {
                "type": "docker",
                "runtime": "3.12"
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command without --keep-dockerfile
    result = runner.invoke(main, ['package', 'lambda_a'])
    assert result.exit_code == 0
    assert not os.path.exists(os.path.join(lambda_path, "Dockerfile"))  # Dockerfile should be deleted

    # Run the package command with --keep-dockerfile
    result = runner.invoke(main, ['package', 'lambda_a', '--keep-dockerfile'])
    assert result.exit_code == 0
    assert os.path.exists(os.path.join(lambda_path, "Dockerfile"))  # Dockerfile should be kept

def test_package_docker_does_not_delete_existing_dockerfile(setup_test_directory):
    """Test that lambda-packer does not delete an existing Dockerfile provided by the user."""
    runner = CliRunner()

    # Simulate a Lambda with an existing Dockerfile
    lambda_path = os.path.join(setup_test_directory, "lambda_a")
    if not os.path.exists(lambda_path):
        os.makedirs(lambda_path)
    with open(os.path.join(lambda_path, "lambda_handler.py"), "w") as f:
        f.write("def lambda_handler(event, context): return 'Hello from Lambda'")

    # Create a user-provided Dockerfile
    with open(os.path.join(lambda_path, "Dockerfile"), "w") as f:
        f.write("FROM python:3.9\n")

    # Create package_config.yaml
    package_config = {
        "lambdas": {
            "lambda_a": {
                "type": "docker",
                "runtime": "3.12"
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command
    result = runner.invoke(main, ['package', 'lambda_a'])
    assert result.exit_code == 0
    assert os.path.exists(os.path.join(lambda_path, "Dockerfile"))  # Dockerfile should not be deleted

def test_package_docker_with_custom_filename_and_function_no_extension_in_cmd(setup_test_directory):
    """Test that lambda-packer generates a Dockerfile with a custom filename and entry function, without .py extension in CMD."""
    runner = CliRunner()

    # Simulate a Lambda with a custom file and function name
    lambda_path = os.path.join(setup_test_directory, "lambda_custom")
    if not os.path.exists(lambda_path):
        os.makedirs(lambda_path)

    # Create custom handler
    with open(os.path.join(lambda_path, "custom_handler.py"), "w") as f:
        f.write("def my_custom_handler(event, context): return 'Hello from custom Lambda'")

    # Create package_config.yaml
    package_config = {
        "lambdas": {
            "lambda_custom": {
                "type": "docker",
                "runtime": "3.9",
                "file_name": "custom_handler.py",
                "function_name": "my_custom_handler",
                "layers": []
            }
        }
    }

    with open("package_config.yaml", "w") as config_file:
        yaml.dump(package_config, config_file)

    # Run the package command with --keep-dockerfile flag
    result = runner.invoke(main, ['package', 'lambda_custom', '--keep-dockerfile'], catch_exceptions=False)
    print(f"Command output:\n{result.output}")  # Debug: Print command output
    assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}"

    # Verify Dockerfile is created before the Docker build process
    dockerfile_path = os.path.join(lambda_path, "Dockerfile")
    assert os.path.exists(dockerfile_path), f"Dockerfile not found at {dockerfile_path}"

    # Check the content of the Dockerfile
    with open(dockerfile_path) as f:
        dockerfile_content = f.read()
    print(f"Dockerfile content:\n{dockerfile_content}")

    # Verify the Dockerfile includes the correct file and function name, without .py in CMD
    assert "COPY custom_handler.py" in dockerfile_content
    assert 'CMD ["custom_handler.my_custom_handler"]' in dockerfile_content  # No .py in CMD
