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
    layer_output_dir = os.path.join(os.getcwd(), 'dist')  # Path to dist directory
    output_file = os.path.join(layer_output_dir, f'{layer_name}.zip')

    # AWS Lambda expects the layer to be structured inside 'python/lib/python3.x/site-packages/'
    layer_temp_dir = os.path.join(os.getcwd(), 'temp_layer')
    python_lib_dir = os.path.join(layer_temp_dir, 'python', 'lib', 'python3.8', 'site-packages')

    # Ensure temp directory and structure exist
    if os.path.exists(layer_temp_dir):
        shutil.rmtree(layer_temp_dir)  # Clean any previous temp files
    os.makedirs(python_lib_dir, exist_ok=True)

    # Copy the entire 'common' directory to the site-packages
    common_dest = os.path.join(python_lib_dir, 'common')
    shutil.copytree(common_path, common_dest)

    # Ensure the 'dist' directory exists
    if not os.path.exists(layer_output_dir):
        os.makedirs(layer_output_dir)

    # Zip the temp_layer directory to create the layer package
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


def package_zip(lambda_name):
    """Package the lambda as a zip file"""
    lambda_path = os.path.join(os.getcwd(), lambda_name)
    output_file = os.path.join(os.getcwd(), 'dist', f'{lambda_name}.zip')

    # Ensure the 'dist' directory exists
    if not os.path.exists(os.path.join(os.getcwd(), 'dist')):
        os.makedirs(os.path.join(os.getcwd(), 'dist'))

    # Zip the Lambda code
    shutil.make_archive(output_file.replace('.zip', ''), 'zip', lambda_path)
    click.echo(f"Lambda {lambda_name} packaged as {output_file}.")


if __name__ == "__main__":
    main()
