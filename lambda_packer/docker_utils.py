import click
from docker.errors import DockerException

from docker import from_env as docker_from_env


def docker_client():
    """Get the Docker client."""
    return docker_from_env()


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
