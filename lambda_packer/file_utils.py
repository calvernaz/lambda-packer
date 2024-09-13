import os
import yaml


def get_common_paths(parent_dir, lambda_name):
    parent_path = os.path.join(os.getcwd(), parent_dir)
    common_dir = os.path.join(parent_path, "common")
    lambda_dir = os.path.join(parent_path, lambda_name)
    dist_dir = os.path.join(parent_path, "dist")
    package_config_path = os.path.join(parent_path, "package_config.yaml")
    return parent_path, common_dir, lambda_dir, dist_dir, package_config_path


def read_yaml(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def write_yaml(file_path, data):
    with open(file_path, "w") as file:
        yaml.dump(data, file, default_flow_style=False)


def file_exists(file_path):
    return os.path.exists(file_path)


def create_file(file_path, content):
    with open(file_path, "w") as file:
        file.write(content)
