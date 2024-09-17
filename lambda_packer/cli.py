import os
import shutil
import subprocess
import sys
from string import Template

import click
import yaml

from lambda_packer.config import Config
from lambda_packer.docker_utils import check_docker_daemon, docker_client
from lambda_packer.file_utils import (
    file_exists,
    config_file_path,
    dist_dir_path,
    abs_to_rel_path,
    COMMON_DIR,
)
from lambda_packer.template_utils import (
    generate_package_config,
    generate_lambda_handler,
)

from lambda_packer.package_utils import (
    package_lambda,
    package_all_lambdas,
    package_layer_internal,
)


@click.group()
def main():
    """Lambda Packer CLI"""
    pass


@click.option("--verbose", is_flag=True, help="Show detailed output.")
@main.command()
def clean(verbose):
    """Clean the 'dist' directory by deleting all files inside it."""
    if not file_exists(config_file_path()):
        click.echo(
            f"Error: '{Config.package_config_yaml}' not found in the current directory. "
            f"Please make sure you're in the correct directory with a valid configuration."
        )
        return

    # Get the relative path of the dist directory
    dist_path = dist_dir_path()

    # Clean up the dist directory
    if file_exists(dist_path) and os.path.isdir(dist_path):
        if verbose:
            click.echo(f"Cleaning {abs_to_rel_path(dist_path)}...")

        shutil.rmtree(dist_path)
        os.makedirs(dist_path)

        if verbose:
            click.echo(f"{abs_to_rel_path(dist_path)} has been cleaned.")
        else:
            click.secho(
                f"Directory '{abs_to_rel_path(dist_path)}' is now clean.", fg="green"
            )
    else:
        click.echo(f"Directory {abs_to_rel_path(dist_path)} does not exist.")


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
    common_dir = os.path.join(parent_path, COMMON_DIR)
    lambda_dir = os.path.join(parent_path, lambda_name)

    # Check if parent directory already exists
    if file_exists(parent_path):
        raise FileExistsError(
            f"Parent directory '{parent_dir}' already exists. Aborting initialization."
        )

    # Create parent, common, lambda, and dist directories
    os.makedirs(common_dir, exist_ok=False)
    os.makedirs(lambda_dir, exist_ok=False)
    os.makedirs(dist_dir_path(parent_path), exist_ok=False)

    # Create a basic package_config.yaml file inside the parent directory
    with open(config_file_path(parent_path), "w") as f:
        f.write(generate_package_config(lambda_name))

    # Create a basic lambda_handler.py in the lambda directory
    lambda_handler_path = os.path.join(lambda_dir, "lambda_handler.py")
    with open(lambda_handler_path, "w") as f:
        f.write(generate_lambda_handler(lambda_name))

    # Create a basic requirements.txt in the lambda directory
    requirements_path = os.path.join(lambda_dir, "requirements.txt")
    with open(requirements_path, "w") as f:
        f.write("# Add your lambda dependencies here\n")

    click.secho("done", fg="green")


@main.command(name="config")
@click.argument("lambda_name", required=False)
@click.option("--repo", default=".", help="Path to the monorepo root directory.")
@click.option(
    "--runtime",
    default=Config.default_python_runtime,
    help="Python runtime version for the lambda",
)
@click.option("--layers", multiple=True, default=[], help="Layers to add to the lambda")
@click.option("--exclude-dirs", multiple=True, default=[], help="Directories to exclude")
def generate_config(repo, lambda_name, runtime, layers, exclude_dirs):
    """Generate a package_config.yaml from an existing monorepo."""

    layers = list(layers)
    exclude_dirs = list(exclude_dirs)

    config_path = config_file_path(repo)
    config_handler = Config(config_path)

    if lambda_name:
        # Add or update a specific lambda in package_config.yaml
        config_handler.config_lambda(lambda_name, layers, runtime)
    else:
        # Configure the entire monorepo
        config_handler.config_repo(layers, exclude_dirs)


@main.command()
@click.argument("lambda_name", required=False)
@click.option(
    "--config", default=Config.package_config_yaml, help="Path to the config file."
)
@click.option(
    "--keep-dockerfile",
    is_flag=True,
    help="Keep the generated Dockerfile after packaging.",
)
@click.pass_context
def package(ctx, lambda_name, config, keep_dockerfile):
    """Package the specified lambda"""
    config_handler = Config(config)
    try:
        config_handler.validate()
    except ValueError as e:
        click.secho(f"{str(e)}", fg="red")
        ctx.exit(1)

    if lambda_name:
        click.secho(f"Packaging lambda '{lambda_name}'...", fg="green")
        package_lambda(lambda_name, config_handler, keep_dockerfile)
    else:
        package_all_lambdas(config_handler, keep_dockerfile)


@main.command(name="package-layer")
@click.argument("layer_name")
def package_layer(layer_name):
    """Package shared dependencies as a lambda layer"""
    package_layer_internal(layer_name)


@main.command("lambda")
@click.argument("lambda_name")
@click.option(
    "--runtime",
    default=Config.default_python_runtime,
    help=f"Python runtime version for the lambda (default: {Config.default_python_runtime})",
)
@click.option(
    "--type", default="zip", help="Packaging type for the lambda (zip or docker)"
)
@click.option("--layers", multiple=True, help="Layers to add to the lambda")
@click.pass_context
def add_lambda(ctx, lambda_name, runtime, type, layers):
    """Add a new lambda to the existing monorepo and update package_config.yaml."""

    # Set up the basic paths
    base_dir = os.getcwd()
    lambda_dir = os.path.join(base_dir, lambda_name)
    package_config_path = os.path.join(base_dir, Config.package_config_yaml)
    config = Config(package_config_path)

    # Check if the Lambda already exists
    if os.path.exists(lambda_dir):
        click.secho(f"Lambda '{lambda_name}' already exists.", fg="red")
        ctx.exit(1)

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

    config.config_lambda(lambda_name, layers, runtime, type)


if __name__ == "__main__":
    main()
