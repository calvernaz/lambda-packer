import os
import shutil
import click
import yaml
from docker import from_env as docker_from_env


@click.group()
def main():
    """Lambda Packer CLI"""
    pass


@main.command()
@click.argument('lambda_name')
@click.option('--config', default='package_config.yaml', help='Path to the config file.')
def package(lambda_name, config):
    """Package the specified lambda"""
    with open(config) as f:
        config_data = yaml.safe_load(f)

    lambda_config = config_data['lambdas'].get(lambda_name)
    if not lambda_config:
        click.echo(f"Lambda {lambda_name} not found in config.")
        return

    if lambda_config['type'] == 'zip':
        package_zip(lambda_name)
    elif lambda_config['type'] == 'docker':
        package_docker(lambda_name)
    else:
        click.echo("Unsupported packaging type")


@main.command(name="package-layer")
@click.argument('layer_name')
def package_layer(layer_name):
    """Package shared dependencies as a lambda layer"""
    common_path = os.path.join(os.getcwd(), 'common')  # Path to common directory
    requirements_path = os.path.join(common_path, 'requirements.txt')  # Path to common requirements.txt
    layer_output_dir = os.path.join(os.getcwd(), 'dist')  # Path to dist directory
    output_file = os.path.join(layer_output_dir, f'{layer_name}.zip')

    # AWS Lambda expects the layer to be structured inside 'python/lib/python3.x/site-packages/'
    layer_temp_dir = os.path.join(os.getcwd(), 'temp_layer')
    python_lib_dir = os.path.join(layer_temp_dir, 'python', 'lib', 'python3.8', 'site-packages')

    # Ensure temp directory and structure exist
    if os.path.exists(layer_temp_dir):
        shutil.rmtree(layer_temp_dir)  # Clean any previous temp files
    os.makedirs(python_lib_dir, exist_ok=True)

    # Step 1: Install dependencies into the site-packages directory if requirements.txt exists
    if os.path.exists(requirements_path):
        click.echo(f"Installing dependencies for {layer_name} from {requirements_path}...")
        subprocess.check_call([os.sys.executable, "-m", "pip", "install", "-r", requirements_path, "-t", python_lib_dir])

    # Step 2: Copy the entire 'common' directory to the site-packages
    common_dest = os.path.join(python_lib_dir, 'common')
    shutil.copytree(common_path, common_dest)

    # Step 3: Ensure the 'dist' directory exists
    if not os.path.exists(layer_output_dir):
        os.makedirs(layer_output_dir)

    # Step 4: Zip the temp_layer directory to create the layer package
    shutil.make_archive(output_file.replace('.zip', ''), 'zip', layer_temp_dir)

    # Clean up temporary directory
    shutil.rmtree(layer_temp_dir)

    click.echo(f"Lambda layer {layer_name} packaged as {output_file}.")



def package_docker(lambda_name):
    """Package the lambda as a docker container"""
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    dockerfile_path = os.path.join(lambda_path, 'Dockerfile')

    if not os.path.exists(dockerfile_path):
        raise FileNotFoundError(f"No Dockerfile found for {lambda_name}")

    docker_client = docker_from_env()
    image_tag = f'{lambda_name}:latest'

    click.echo(f"Building Docker image for {lambda_name}...")

    try:
        # Build the Docker image and stream logs
        build_output = docker_client.api.build(path=lambda_path, tag=image_tag, rm=True, decode=True)

        for log in build_output:
            if 'stream' in log:
                click.echo(log['stream'].strip())
            elif 'error' in log:
                click.echo(f"Error: {log['error']}")
                raise Exception(log['error'])
    except Exception as e:
        click.echo(f"Error during Docker build: {str(e)}")
        raise

    click.echo(f"Lambda {lambda_name} packaged as Docker container {image_tag}.")


import subprocess

def package_zip(lambda_name):
    """Package the lambda as a zip file including dependencies"""
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    requirements_path = os.path.join(lambda_path, 'requirements.txt')
    build_dir = os.path.join(lambda_path, 'build')
    output_file = os.path.join(os.getcwd(), 'dist', f'{lambda_name}.zip')

    # Ensure the 'dist' directory exists
    if not os.path.exists(os.path.join(os.getcwd(), 'dist')):
        os.makedirs(os.path.join(os.getcwd(), 'dist'))

    # Ensure the build directory is clean
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    # Step 1: Install dependencies into the build directory if requirements.txt exists
    if os.path.exists(requirements_path):
        click.echo(f"Installing dependencies for {lambda_name} from {requirements_path}...")
        subprocess.check_call([os.sys.executable, "-m", "pip", "install", "-r", requirements_path, "-t", build_dir])

    # Step 2: Copy lambda source files (excluding requirements.txt) to the build directory
    for item in os.listdir(lambda_path):
        if item != 'build' and item != 'requirements.txt':
            s = os.path.join(lambda_path, item)
            d = os.path.join(build_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    # Step 3: Create a ZIP file from the build directory
    shutil.make_archive(output_file.replace('.zip', ''), 'zip', build_dir)

    # Step 4: Clean up the build directory
    shutil.rmtree(build_dir)

    click.echo(f"Lambda {lambda_name} packaged as {output_file}.")


if __name__ == "__main__":
    main()
