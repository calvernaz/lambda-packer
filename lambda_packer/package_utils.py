import os
import shutil
import subprocess
from string import Template

import click

from lambda_packer.config import Config
from lambda_packer.docker_utils import check_docker_daemon, docker_client
from lambda_packer.file_utils import (
    file_exists,
    abs_to_rel_path,
    ensure_directory_exists,
)

DOCKERFILE_TEMPLATE = Template(
    """
FROM public.ecr.aws/lambda/python:$runtime

COPY . $${LAMBDA_TASK_ROOT}/

# Install dependencies for the Lambda function if requirements.txt is present
RUN if [ -f $${LAMBDA_TASK_ROOT}/requirements.txt ]; then \\
        pip install --no-cache-dir -r requirements.txt -t $${LAMBDA_TASK_ROOT}; \\
    else \\
        echo "Warning: No requirements.txt found. Skipping dependency installation."; \\
    fi

$layer_dependencies

CMD ["$file_base_name.$function_name"]
"""
)


def package_layer_internal(layer_name, runtime=Config.default_python_runtime):
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

    ensure_directory_exists(python_lib_dir)
    # Install dependencies into the site-packages directory if requirements.txt exists
    install_dependencies(requirements_path, python_lib_dir)

    # Copy the entire layer directory to the site-packages
    layer_dest = os.path.join(python_lib_dir, layer_name)
    shutil.copytree(common_path, layer_dest)

    # Zip the temp_layer directory to create the layer package
    shutil.make_archive(output_file.replace(".zip", ""), "zip", layer_temp_dir)

    # Clean up temporary directory
    shutil.rmtree(layer_temp_dir)

    click.secho(
        f"Lambda layer {layer_name} packaged as {abs_to_rel_path(output_file)}.",
        fg="green",
    )


def package_lambda(lambda_name, config_handler, keep_dockerfile):
    """Package a single lambda based on its type (zip or docker)."""
    lambda_config = config_handler.get_lambda_config(lambda_name)
    if not lambda_config:
        click.echo(f"Lambda {lambda_name} not found in config.")
        return

    lambda_type = lambda_config.get("type")
    if "docker" in lambda_type:
        package_docker(lambda_name, config_handler, keep_dockerfile)
    else:
        package_zip(lambda_name, config_handler)


def package_all_lambdas(config_handler, keep_dockerfile):
    """Package all lambdas defined in the config."""
    lambdas = config_handler.get_lambdas()
    for lambda_name, lambda_config in lambdas.items():
        click.echo(
            f"Packaging lambda '{lambda_name}' of type '{lambda_config.get('type', 'zip')}'..."
        )
        package_lambda(lambda_name, config_handler, keep_dockerfile)
    click.echo(f"Finished packaging all lambdas in {config_handler.config_path}.")


def package_docker(lambda_name, config_handler, keep_dockerfile):
    """Package the lambda as a docker container, using image tag from config if provided"""
    if not check_docker_daemon():
        return

    lambda_path = os.path.join(os.getcwd(), lambda_name)
    lambda_config = config_handler.get_lambda_config(lambda_name)
    layers = config_handler.get_lambda_layers(lambda_name)
    target_platforms = config_handler.get_lambda_platforms(lambda_name)

    dockerfile_path = os.path.join(lambda_path, "Dockerfile")
    image_tag = lambda_config.get("image", f"{lambda_name}:latest")
    lambda_runtime = lambda_config.get("runtime", Config.default_python_runtime)
    file_name = lambda_config.get("file_name", Config.default_lambda_filename)
    function_name = lambda_config.get("function_name", "lambda_handler")

    file_base_name = os.path.splitext(file_name)[0]
    dockerfile_generated = False

    # Generate a Dockerfile if none exists
    if not file_exists(dockerfile_path):
        click.echo(
            f"No Dockerfile found for {lambda_name}. Generating default Dockerfile..."
        )

        dockerfile_generated = True
        # Dynamically generate COPY and RUN statements for layers
        layer_dependencies = ""

        for layer_name in layers:
            layer_dependencies += f"RUN if [ -f '${{LAMBDA_TASK_ROOT}}/{layer_name}/requirements.txt' ]; then \\\n"
            layer_dependencies += f"    pip install --no-cache-dir -r ${{LAMBDA_TASK_ROOT}}/{layer_name}/requirements.txt -t ${{LAMBDA_TASK_ROOT}}; \\\n"
            layer_dependencies += "else \\\n"
            layer_dependencies += f"    echo 'Warning: No requirements.txt found for {layer_name}. Skipping dependency installation.'; \\\n"
            layer_dependencies += "fi\n"

        # Substitute values into the template
        dockerfile_content = DOCKERFILE_TEMPLATE.substitute(
            runtime=lambda_runtime,
            file_base_name=file_base_name,
            function_name=function_name,
            layer_dependencies=layer_dependencies,
        )

        try:
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
            click.secho(
                f"Dockerfile successfully generated at {abs_to_rel_path(dockerfile_path)}",
                fg="green",
            )
        except Exception as e:
            click.secho(f"Failed to generate Dockerfile: {str(e)}", fg="red")

    layer_dirs_to_remove = []

    for layer_name in layers:
        layer_path = os.path.join(
            os.path.dirname(config_handler.config_path), layer_name
        )
        requirements_path = os.path.join(layer_path, "requirements.txt")

        # Ensure layer directory exists
        if not os.path.exists(layer_path):
            raise FileNotFoundError(f"Layer directory {layer_path} not found")

        # Copy the layer code into the Docker image directory (e.g., into /var/task/{layer_name})
        layer_dest = os.path.join(lambda_path, layer_name)
        # Remove the existing layer directory if it exists
        if os.path.exists(layer_dest):
            shutil.rmtree(layer_dest)

        click.echo(f"Copying layer '{layer_name}' to '{abs_to_rel_path(layer_dest)}'")
        shutil.copytree(layer_path, layer_dest)
        layer_dirs_to_remove.append(layer_dest)

        install_dependencies(requirements_path, layer_dest)

    # Build the Docker image
    try:
        for target_platform in target_platforms:
            build_output = docker_client().api.build(
                path=lambda_path,
                tag=image_tag,
                platform=target_platform,
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
        for layer_dir in layer_dirs_to_remove:
            click.echo(f"Removing layer directory: {layer_dir}")
            shutil.rmtree(layer_dir)

        if (
            dockerfile_generated
            and not keep_dockerfile
            and os.path.exists(dockerfile_path)
        ):
            click.echo(f"Removing generated Dockerfile for {lambda_name}")
            os.remove(dockerfile_path)

    click.echo(
        f"Lambda '{lambda_name}' packaged as Docker container with tag '{image_tag}'."
    )


def package_zip(lambda_name, config_handler):
    """Package the lambda as a zip file including dependencies"""
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    requirements_path = os.path.join(lambda_path, "requirements.txt")
    build_dir = os.path.join(lambda_path, "build")
    output_file = os.path.join(os.getcwd(), "dist", f"{lambda_name}.zip")

    # Clean up the build directory
    shutil.rmtree(build_dir, ignore_errors=True)

    # Ensure the 'dist' directory exists
    ensure_directory_exists(os.path.join(os.getcwd(), "dist"))
    ensure_directory_exists(build_dir)

    install_dependencies(requirements_path, build_dir)

    # Copy lambda source files (excluding requirements.txt) to the build directory
    for item in os.listdir(lambda_path):
        if item not in ["build", "requirements.txt"]:
            s = os.path.join(lambda_path, item)
            d = os.path.join(build_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    if config_handler.should_bundle_layers(lambda_name):
        # Include the entire layers in the main zip file (copying full directories)
        for layer_name in config_handler.get_lambda_layers(lambda_name):
            click.echo(f"Including layer {layer_name} in the zip.")
            layer_path = os.path.join(os.getcwd(), layer_name)
            layer_dest_path = os.path.join(build_dir, layer_name)

            # Copy the full layer directory into the 'layers' subdirectory in build_dir
            shutil.copytree(layer_path, layer_dest_path)
    else:
        # Package layers separately if bundle_layers is False
        for layer_name in config_handler.get_lambda_layers(lambda_name):
            click.echo(f"Packaging layer separately: {layer_name}")
            runtime = config_handler.get_lambda_runtime(lambda_name)
            package_layer_internal(layer_name, runtime)

    # Create a ZIP file from the build directory
    shutil.make_archive(output_file.replace(".zip", ""), "zip", build_dir)

    # Include the layers referenced in the config
    for layer_name in config_handler.get_lambda_layers(lambda_name):
        click.echo(f"Packaging layer_name: {layer_name}")
        runtime = config_handler.get_lambda_runtime(lambda_name)
        package_layer_internal(layer_name, runtime)

    click.secho(
        f"Lambda {lambda_name} packaged as {abs_to_rel_path(output_file)}.", fg="green"
    )


def install_dependencies(requirements_path, target_dir):
    if os.path.exists(requirements_path):
        click.echo(
            f"Installing dependencies from {abs_to_rel_path(requirements_path)}..."
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
                target_dir,
            ]
        )
