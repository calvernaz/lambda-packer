import os
import shutil
import subprocess
import sys
from string import Template

import click
import yaml
from docker import from_env as docker_from_env
from docker.errors import DockerException

from lambda_packer.config import Config

DOCKERFILE_TEMPLATE = Template("""
FROM public.ecr.aws/lambda/python:$runtime

# Copy function code
COPY $file_name $${LAMBDA_TASK_ROOT}/$file_name

$layer_copy

# Install dependencies for the Lambda function if requirements.txt is present
RUN if [ -f "requirements.txt" ]; then \\
        pip install --no-cache-dir -r requirements.txt -t $${LAMBDA_TASK_ROOT}; \\
    else \\
        echo "Warning: No requirements.txt found. Skipping dependency installation."; \\
    fi

$layer_dependencies

# Specify the Lambda handler
CMD ["$file_base_name.$function_name"]
""")



@click.group()
def main():
    """Lambda Packer CLI"""
    pass


@click.option('--verbose', is_flag=True, help="Show detailed output.")
@main.command()
def clean(verbose):
    """Clean the 'dist' directory by deleting all files inside it."""
    config_path = os.path.join(os.getcwd(), "package_config.yaml")

    if not os.path.exists(config_path):
        click.echo(f"Error: 'package_config.yaml' not found in the current directory. "
                   f"Please make sure you're in the correct monorepo directory with a valid configuration.")
        return

    # Get the relative path of the dist directory
    dist_path = os.path.join(os.path.dirname(config_path), "dist")

    # Clean up the dist directory
    if os.path.exists(dist_path) and os.path.isdir(dist_path):
        if verbose:
            click.echo(f"Cleaning {os.path.relpath(dist_path)}...")

        shutil.rmtree(dist_path)
        os.makedirs(dist_path)

        if verbose:
            click.echo(f"{os.path.relpath(dist_path)} has been cleaned.")
        else:
            click.echo(f"Cleaned the 'dist' directory.")
    else:
        click.echo(f"Directory {os.path.relpath(dist_path)} does not exist.")


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


@main.command(name="config")
@click.argument("lambda_name", required=False)
@click.option("--repo", default=".", help="Path to the monorepo root directory.")
def generate_config(repo, lambda_name):
    """Generate a package_config.yaml from an existing monorepo."""

    config_path = os.path.join(repo, "package_config.yaml")

    # Step 1: Ensure package_config.yaml exists or create a new one if generating for the first time
    if os.path.exists(config_path):
        with open(config_path, "r") as config_file:
            package_config = yaml.safe_load(config_file) or {"lambdas": {}}
    else:
        package_config = {"lambdas": {}}

    if lambda_name:
        # Step 2: Add or update a specific lambda in package_config.yaml
        add_lambda_to_config(lambda_name, package_config, repo, config_path)
    else:
        # Step 3: If no lambda name is provided, configure the entire monorepo
        configure_entire_monorepo(package_config, repo, config_path)


def add_lambda_to_config(lambda_name, package_config, monorepo_path, config_path):
    """Add a specific lambda to package_config.yaml."""
    lambda_path = os.path.join(monorepo_path, lambda_name)

    # Check if the lambda directory exists
    if not os.path.exists(lambda_path):
        click.echo(f"Error: Lambda '{lambda_name}' not found in {monorepo_path}.")
        return

    # Check if the lambda is already in the config
    if lambda_name in package_config.get("lambdas", {}):
        click.echo(
            f"Lambda '{lambda_name}' is already included in package_config.yaml."
        )
        return

    # Determine lambda type (zip or docker)
    lambda_type = (
        "docker" if os.path.exists(os.path.join(lambda_path, "Dockerfile")) else "zip"
    )

    # Add the lambda to the config
    package_config["lambdas"][lambda_name] = {
        "type": lambda_type,
        "runtime": "3.8",  # Default runtime
    }

    # Save the updated config
    with open(config_path, "w") as config_file:
        yaml.dump(package_config, config_file, default_flow_style=False)

    click.echo(f"Lambda '{lambda_name}' has been added to package_config.yaml.")


def configure_entire_monorepo(package_config, monorepo_path, config_path):
    """Scan the entire monorepo and add all detected lambdas to package_config.yaml."""
    lambdas = package_config.get("lambdas", {})

    # Scan for lambdas
    for root, dirs, files in os.walk(monorepo_path):
        if "lambda_handler.py" in files or "Dockerfile" in files:
            lambda_name = os.path.basename(root)
            if lambda_name not in lambdas:
                lambda_type = "docker" if "Dockerfile" in files else "zip"
                lambdas[lambda_name] = {
                    "type": lambda_type,
                    "runtime": "3.8",  # Default runtime
                }

    package_config["lambdas"] = lambdas

    # Save the updated config
    with open(config_path, "w") as config_file:
        yaml.dump(package_config, config_file, default_flow_style=False)

    click.echo(f"Updated package_config.yaml with {len(lambdas)} lambda(s).")


@main.command()
@click.argument("lambda_name", required=False)
@click.option(
    "--config", default="package_config.yaml", help="Path to the config file."
)
@click.option(
    "--keep-dockerfile",
    is_flag=True,
    help="Keep the generated Dockerfile after packaging.",
)
def package(lambda_name, config, keep_dockerfile):
    """Package the specified lambda"""
    config_handler = Config(config)
    try:
        config_handler.validate()
    except ValueError as e:
        click.echo(str(e))
        sys.exit(1)

    if lambda_name:
        lambda_config = config_handler.get_lambda_config(lambda_name)
        if not lambda_config:
            click.echo(f"Lambda {lambda_name} not found in config.")
            return
        click.echo(f"Packaging lambda '{lambda_name}'...")
        package_individual_lambda(lambda_name, lambda_config, config_handler, keep_dockerfile)
    else:
        lambdas = config_handler.get_lambdas()
        for lambda_name, lambda_config in lambdas.items():
            click.echo(
                f"Packaging lambda '{lambda_name}' of type '{lambda_config.get('type', 'zip')}'..."
            )
            package_individual_lambda(lambda_name, lambda_config, config_handler, keep_dockerfile)
        click.echo(f"Finished packaging all lambdas in {config}.")


def package_individual_lambda(lambda_name, lambda_config, config, keep_dockerfile):
    """Package a single lambda, either zip or docker."""
    lambda_type = lambda_config.get("type", "zip")

    if lambda_type == "docker":
        try:
            package_docker(
                lambda_name, config, keep_dockerfile
            )  # Assuming Config is a helper class for config handling
        except Exception as e:
            click.echo(f"Failed to package Docker lambda '{lambda_name}': {str(e)}")
    else:
        try:
            package_zip(
                lambda_name, config
            )  # Assuming package_zip is a function for zip lambdas
        except Exception as e:
            click.echo(f"Failed to package Zip lambda '{lambda_name}': {str(e)}")


@main.command(name="package-layer")
@click.argument("layer_name")
def package_layer(layer_name):
    """Package shared dependencies as a lambda layer"""
    package_layer_internal(layer_name)


def package_docker(lambda_name, config_handler, keep_dockerfile):
    """Package the lambda as a docker container, using image tag from config if provided"""
    if not check_docker_daemon():
        return

    lambda_config = config_handler.get_lambda_config(lambda_name)
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    layers = config_handler.get_lambda_layers(lambda_name)

    dockerfile_path = os.path.join(lambda_path, "Dockerfile")
    image_tag = lambda_config.get("image", f"{lambda_name}:latest")
    lambda_runtime = lambda_config.get("runtime", "3.12")
    target_arch = lambda_config.get("arch", "linux/amd64")
    file_name = lambda_config.get('file_name', 'lambda_handler.py')
    function_name = lambda_config.get('function_name', 'lambda_handler')

    file_base_name = os.path.splitext(file_name)[0]
    dockerfile_generated = False

    # Step 1: Generate a Dockerfile if none exists
    if not os.path.exists(dockerfile_path):
        click.echo(
            f"No Dockerfile found for {lambda_name}. Generating default Dockerfile..."
        )

        dockerfile_generated = True
        # Dynamically generate COPY and RUN statements for layers
        layer_copy = ""
        layer_dependencies = ""

        for layer_name in layers:
            # Add COPY for each layer
            layer_copy += f"COPY ./{layer_name} ${{LAMBDA_TASK_ROOT}}/{layer_name}\n"
            # Add RUN for each layer's requirements.txt if it exists
            layer_dependencies += f"RUN if [ -f '${{LAMBDA_TASK_ROOT}}/{layer_name}/requirements.txt' ]; then \\\n"
            layer_dependencies += f"    pip install --no-cache-dir -r ${{LAMBDA_TASK_ROOT}}/{layer_name}/requirements.txt -t ${{LAMBDA_TASK_ROOT}}; \\\n"
            layer_dependencies += f"else \\\n"
            layer_dependencies += f"    echo 'Warning: No requirements.txt found for {layer_name}. Skipping dependency installation.'; \\\n"
            layer_dependencies += f"fi\n"

        # Substitute values into the template
        dockerfile_content = DOCKERFILE_TEMPLATE.substitute(
            runtime=lambda_runtime,
            file_name=file_name,
            file_base_name=file_base_name,
            function_name=function_name,
            layer_copy=layer_copy,
            layer_dependencies=layer_dependencies
        )

        try:
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
            click.echo(f"Dockerfile successfully generated at {dockerfile_path}")
        except Exception as e:
            click.echo(f"Failed to generate Dockerfile: {str(e)}")


    click.echo(
        f"Building Docker image for {lambda_name} with tag {image_tag} and architecture {target_arch}..."
    )

    docker_client = docker_from_env()

    # Step 2: Prepare layer files and dependencies for the Docker image
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

    # Step 3: Build the Docker image with the specified architecture
    try:
        build_output = docker_client.api.build(
            path=lambda_path,
            tag=image_tag,
            platform=target_arch,
            rm=True,
            decode=True,
            nocache=True,
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

        if dockerfile_generated and not keep_dockerfile:
            if os.path.exists(dockerfile_path):
                click.echo(f"Removing generated Dockerfile for {lambda_name}")
                os.remove(dockerfile_path)

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


@main.command("lambda")
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


def check_docker_daemon():
    """Check if the Docker daemon is running."""
    try:
        docker_client = docker_from_env()
        docker_client.ping()
        return True
    except DockerException:
        click.echo(
            "Error: Docker daemon is not running. Please start the Docker daemon and try again."
        )
        return False


if __name__ == "__main__":
    main()
