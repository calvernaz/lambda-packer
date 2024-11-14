import os
import shutil

import click

from lambda_packer.config import Config
from lambda_packer.file_utils import (
    file_exists,
    config_file_path,
    dist_dir_path,
    abs_to_rel_path,
    COMMON_DIR,
    create_directory,
    write_to_file,
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

    # Check if the parent directory already exists
    if file_exists(parent_path):
        raise FileExistsError(
            f"Parent directory '{parent_dir}' already exists. Aborting initialization."
        )

    # Create parent, common, lambda, and dist directories
    create_directory(common_dir)
    create_directory(lambda_dir)
    create_directory(dist_dir_path(parent_path))

    # Create the package_config.yaml file
    write_to_file(config_file_path(parent_path), generate_package_config(lambda_name))
    # Create the lambda .py file
    write_to_file(
        os.path.join(lambda_dir, Config.default_lambda_filename),
        generate_lambda_handler(lambda_name),
    )
    # Create the requirements.txt file
    write_to_file(
        os.path.join(lambda_dir, Config.default_requirements_filename),
        "# Add your lambda dependencies here\n",
    )

    click.secho("Initialization complete. Your project is ready to go!", fg="green")


@main.command(name="config")
@click.argument("lambda_name", required=False)
@click.option("--repo", default=".", help="Path to the monorepo root directory.")
@click.option(
    "--runtime",
    default=Config.default_python_runtime,
    help="Python runtime version for the lambda",
)
@click.option("--layers", multiple=True, default=[], help="Layers to add to the lambda")
@click.option(
    "--exclude-dirs", multiple=True, default=[], help="Directories to exclude"
)
def generate_config(repo, lambda_name, runtime, layers, exclude_dirs):
    """Generate a package_config.yaml from an existing monorepo."""

    layers = list(layers)
    config_path = config_file_path(repo)
    config_handler = Config(config_path)

    if lambda_name:
        # Add or update a specific lambda in package_config.yaml
        config_handler.config_lambda(lambda_name, layers, runtime)
    else:
        exclude_dirs = list(exclude_dirs)

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
@click.option("--layers", multiple=True, help="Layers to add to the lambda")
@click.option(
    "--runtime",
    default=Config.default_python_runtime,
    help=f"Python runtime version for the lambda (default: {Config.default_python_runtime})",
)
@click.option(
    "--type", multiple=True, help="Packaging type for the lambda (zip or docker)"
)
@click.option(
    "--platforms", multiple=True, help="Target platform for the lambda (x86_64, arm64)"
)
@click.pass_context
def add_lambda(ctx, lambda_name, runtime, type, layers, platforms):
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
    create_directory(lambda_dir)

    write_to_file(
        os.path.join(lambda_dir, Config.default_lambda_filename),
        generate_lambda_handler(lambda_name),
    )
    write_to_file(
        os.path.join(lambda_dir, Config.default_requirements_filename),
        "# Add your lambda dependencies here\n",
    )

    if not type:
        type = [config.default_package_type]
    if not platforms:
        platforms = config.default_platforms

    config.config_lambda(
        lambda_name, list(layers), runtime, list(type), list(platforms)
    )


if __name__ == "__main__":
    main()
