import os
import shutil
import subprocess
import sys

import click
import yaml
from docker import from_env as docker_from_env

from lambda_packer.config import Config


@click.group()
def main():
    """Lambda Packer CLI"""
    pass


@main.command()
def clean():
    """Clean the dist directory by deleting all files inside it."""
    dist_path = os.path.join(os.getcwd(), "dist")

    if os.path.exists(dist_path) and os.path.isdir(dist_path):
        click.echo(f"Cleaning {dist_path}...")
        # Remove everything inside the dist directory
        shutil.rmtree(dist_path)
        os.makedirs(dist_path)  # Recreate the dist directory after cleaning
        click.echo(f"{dist_path} has been cleaned.")
    else:
        click.echo(f"Directory {dist_path} does not exist.")


@main.command()
@click.argument("parent_dir")
@click.option(
    "--lambda-name",
    default="lambda_example",
    help="Lambda function name (default: lambda_example)",
)
def init(parent_dir, lambda_name):
    """Initialize a monorepo with a given parent directory and lambda name."""

    # Set base directory paths inside the parent directory
    parent_path = os.path.join(os.getcwd(), parent_dir)
    common_dir = os.path.join(parent_path, "common")
    lambda_dir = os.path.join(parent_path, lambda_name)
    dist_dir = os.path.join(parent_path, "dist")
    package_config_path = os.path.join(parent_path, "package_config.yaml")

    # Check if parent directory already exists
    if os.path.exists(parent_path):
        raise FileExistsError(
            f"Parent directory '{parent_dir}' already exists. Aborting initialization."
        )

    # Create parent, common, lambda, and dist directories
    os.makedirs(common_dir, exist_ok=False)
    os.makedirs(lambda_dir, exist_ok=False)
    os.makedirs(dist_dir, exist_ok=False)

    # Create a basic package_config.yaml file inside the parent directory
    package_config_content = f"""lambdas:
  {lambda_name}:
    type: zip
    layers:
      - common
"""

    with open(package_config_path, "w") as f:
        f.write(package_config_content)

    # Create a basic lambda_handler.py in the lambda directory
    lambda_handler_path = os.path.join(lambda_dir, "lambda_handler.py")
    lambda_handler_content = f"""def lambda_handler(event, context):
    return {{
        'statusCode': 200,
        'body': 'Hello from {lambda_name}!'
    }}
"""

    with open(lambda_handler_path, "w") as f:
        f.write(lambda_handler_content)

    # Create a basic requirements.txt in the lambda directory
    requirements_path = os.path.join(lambda_dir, "requirements.txt")
    with open(requirements_path, "w") as f:
        f.write("# Add your lambda dependencies here\n")

    click.echo("done")


@main.command()
@click.argument("lambda_name")
@click.option(
    "--config", default="package_config.yaml", help="Path to the config file."
)
def package(lambda_name, config):
    """Package the specified lambda"""
    config_handler = Config(config)
    try:
        config_handler.validate()
    except ValueError as e:
        click.echo(str(e))
        sys.exit(1)

    lambda_config = config_handler.get_lambda_config(lambda_name)
    if not lambda_config:
        click.echo(f"Lambda {lambda_name} not found in config.")
        return

    if lambda_config["type"] == "zip":
        package_zip(lambda_name, config_handler)  # Pass the config data object here
    elif lambda_config["type"] == "docker":
        package_docker(lambda_name, config_handler)  # Pass the config data object here
    else:
        click.echo("Unsupported packaging type")


@main.command(name="package-layer")
@click.argument("layer_name")
def package_layer(layer_name):
    """Package shared dependencies as a lambda layer"""
    package_layer_internal(layer_name)


def package_docker(lambda_name, config_handler):
    """Package the lambda as a docker container, using image tag from config if provided"""
    lambda_config = config_handler.get_lambda_config(lambda_name)
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    dockerfile_path = os.path.join(lambda_path, "Dockerfile")

    # Ensure Dockerfile exists
    if not os.path.exists(dockerfile_path):
        raise FileNotFoundError(f"No Dockerfile found for {lambda_name}")

    # Read the architecture from the config (default to linux/amd64 if not specified)
    target_arch = lambda_config.get("arch", "linux/amd64")
    image_tag = lambda_config.get("image", f"{lambda_name}:latest")

    docker_client = docker_from_env()

    click.echo(
        f"Building Docker image for {lambda_name} with tag {image_tag} and architecture {target_arch}..."
    )

    # Step 1: Prepare layer files and dependencies for the Docker image
    layer_dirs_to_remove = []  # Keep track of the layer directories to remove later

    for layer_name in config_handler.get_lambda_layers(lambda_name):
        layer_path = os.path.join(os.getcwd(), layer_name)
        requirements_path = os.path.join(layer_path, "requirements.txt")

        # Ensure layer directory exists
        if not os.path.exists(layer_path):
            raise FileNotFoundError(f"Layer directory {layer_path} not found")

        # Step 1a: Copy the layer code into the Docker image directory (e.g., into /var/task/{layer_name})
        layer_dest = os.path.join(lambda_path, layer_name)
        shutil.copytree(layer_path, layer_dest)
        layer_dirs_to_remove.append(layer_dest)  # Track the directory to remove later
        click.echo(f"Copied {layer_name} to the Docker image")

        # Step 1b: Install dependencies for the layer if requirements.txt is present
        if os.path.exists(requirements_path):
            click.echo(f"Installing dependencies for layer {layer_name}...")
            subprocess.check_call(
                [
                    os.sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    requirements_path,
                    "-t",
                    layer_dest,
                ]
            )

    # Step 2: Build the Docker image with the specified architecture
    try:
        build_output = docker_client.api.build(
            path=lambda_path, tag=image_tag, platform=target_arch, rm=True, decode=True
        )

        for log in build_output:
            if "stream" in log:
                click.echo(log["stream"].strip())
            elif "error" in log:
                click.echo(f"Error: {log['error']}")
                raise Exception(log["error"])
    except Exception as e:
        click.echo(f"Error during Docker build: {str(e)}")
        raise
    finally:
        # Step 3: Clean up - Remove the layer directories from the Lambda's directory
        for layer_dir in layer_dirs_to_remove:
            click.echo(f"Removing layer directory: {layer_dir}")
            shutil.rmtree(layer_dir)

    click.echo(
        f"Lambda {lambda_name} packaged as Docker container with tag {image_tag}."
    )


def package_zip(lambda_name, config_handler):
    """Package the lambda as a zip file including dependencies"""
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    requirements_path = os.path.join(lambda_path, "requirements.txt")
    build_dir = os.path.join(lambda_path, "build")
    output_file = os.path.join(os.getcwd(), "dist", f"{lambda_name}.zip")

    # Ensure the 'dist' directory exists
    if not os.path.exists(os.path.join(os.getcwd(), "dist")):
        os.makedirs(os.path.join(os.getcwd(), "dist"))

    # Ensure the build directory is clean
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    # Step 1: Install dependencies into the build directory if requirements.txt exists
    if os.path.exists(requirements_path):
        click.echo(
            f"Installing dependencies for {lambda_name} from {requirements_path}..."
        )
        subprocess.check_call(
            [
                os.sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                requirements_path,
                "-t",
                build_dir,
            ]
        )

    # Step 2: Copy lambda source files (excluding requirements.txt) to the build directory
    for item in os.listdir(lambda_path):
        if item != "build" and item != "requirements.txt":
            s = os.path.join(lambda_path, item)
            d = os.path.join(build_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    # Step 3: Create a ZIP file from the build directory
    shutil.make_archive(output_file.replace(".zip", ""), "zip", build_dir)

    # Step 4: Clean up the build directory
    shutil.rmtree(build_dir)

    # Include the layers referenced in the config
    for layer_name in config_handler.get_lambda_layers(lambda_name):
        click.echo(f"Packaging layer_name: {layer_name}")
        runtime = config_handler.get_lambda_runtime(lambda_name)
        package_layer_internal(layer_name, runtime)

    click.echo(f"Lambda {lambda_name} packaged as {output_file}.")


@main.command()
@click.argument("lambda_name")
@click.option(
    "--runtime",
    default="3.8",
    help="Python runtime version for the lambda (default: 3.8)",
)
@click.option(
    "--type", default="zip", help="Packaging type for the lambda (zip or docker)"
)
@click.option("--layers", multiple=True, help="Layers to add to the lambda")
def add_lambda(lambda_name, runtime, type, layers):
    """Add a new lambda to the existing monorepo and update package_config.yaml."""

    # Set up the basic paths
    base_dir = os.getcwd()
    lambda_dir = os.path.join(base_dir, lambda_name)
    package_config_path = os.path.join(base_dir, "package_config.yaml")

    # Check if the Lambda already exists
    if os.path.exists(lambda_dir):
        raise FileExistsError(f"Lambda '{lambda_name}' already exists.")

    # Create the lambda directory and necessary files
    os.makedirs(lambda_dir)

    # Create a basic lambda_handler.py
    lambda_handler_path = os.path.join(lambda_dir, "lambda_handler.py")
    lambda_handler_content = f"""def lambda_handler(event, context):
    return {{
        'statusCode': 200,
        'body': 'Hello from {lambda_name}!'
    }}
"""
    with open(lambda_handler_path, "w") as f:
        f.write(lambda_handler_content)

    # Create a basic requirements.txt
    requirements_path = os.path.join(lambda_dir, "requirements.txt")
    with open(requirements_path, "w") as f:
        f.write("# Add your lambda dependencies here\n")

    # Update the package_config.yaml file
    if not os.path.exists(package_config_path):
        raise FileNotFoundError(f"package_config.yaml not found at {base_dir}")

    with open(package_config_path, "r") as f:
        config_data = yaml.safe_load(f)

    # Add the new Lambda to the package_config.yaml
    if "lambdas" not in config_data:
        config_data["lambdas"] = {}

    new_lambda_config = {"type": type, "runtime": runtime}

    # Add layers if specified
    if layers:
        new_lambda_config["layers"] = list(layers)

    config_data["lambdas"][lambda_name] = new_lambda_config

    # Write the updated config back to package_config.yaml
    with open(package_config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    click.echo(
        f"Lambda '{lambda_name}' added with runtime {runtime}, type {type}, and layers {layers}."
    )


def package_layer_internal(layer_name, runtime="3.8"):
    """Package shared dependencies as a lambda layer (internal function)"""
    common_path = os.path.join(os.getcwd(), layer_name)  # Path to layer directory
    requirements_path = os.path.join(
        common_path, "requirements.txt"
    )  # Path to requirements.txt
    layer_output_dir = os.path.join(os.getcwd(), "dist")  # Path to dist directory
    output_file = os.path.join(layer_output_dir, f"{layer_name}.zip")

    # AWS Lambda expects the layer to be structured inside 'python/lib/python3.x/site-packages/'
    python_runtime = f"python{runtime}"
    layer_temp_dir = os.path.join(os.getcwd(), "temp_layer")
    python_lib_dir = os.path.join(
        layer_temp_dir, f"python/lib/{python_runtime}/site-packages"
    )

    # Ensure temp directory and structure exist
    if os.path.exists(layer_temp_dir):
        shutil.rmtree(layer_temp_dir)  # Clean any previous temp files
    os.makedirs(python_lib_dir, exist_ok=True)

    # Step 1: Install dependencies into the site-packages directory if requirements.txt exists
    if os.path.exists(requirements_path):
        click.echo(
            f"Installing dependencies for {layer_name} from {requirements_path}..."
        )
        subprocess.check_call(
            [
                os.sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                requirements_path,
                "-t",
                python_lib_dir,
            ]
        )

    # Step 2: Copy the entire layer directory to the site-packages
    layer_dest = os.path.join(python_lib_dir, layer_name)
    shutil.copytree(common_path, layer_dest)

    # Step 3: Ensure the 'dist' directory exists
    if not os.path.exists(layer_output_dir):
        os.makedirs(layer_output_dir)

    # Step 4: Zip the temp_layer directory to create the layer package
    shutil.make_archive(output_file.replace(".zip", ""), "zip", layer_temp_dir)

    # Clean up temporary directory
    shutil.rmtree(layer_temp_dir)

    click.echo(f"Lambda layer {layer_name} packaged as {output_file}.")


if __name__ == "__main__":
    main()
