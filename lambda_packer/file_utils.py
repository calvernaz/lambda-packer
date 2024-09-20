import os
import shutil

import yaml

from lambda_packer.config import Config

DIST_DIR: str = "dist"
COMMON_DIR: str = "common"


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


def create_directory(path, exist_ok=True):
    try:
        os.makedirs(path, exist_ok=exist_ok)
    except FileExistsError as e:
        raise FileExistsError(f"Directory '{path}' already exists.") from e


def write_to_file(path, content):
    with open(path, "w") as f:
        f.write(content)


def abs_to_rel_path(abs_path):
    return os.path.relpath(abs_path)


def create_file(file_path, content):
    with open(file_path, "w") as file:
        file.write(content)


def config_file_path(repo: str = os.getcwd()) -> str:
    return os.path.join(repo, Config.package_config_yaml)


def dist_dir_path(repo: str = os.getcwd()) -> str:
    return os.path.join(os.path.dirname(config_file_path(repo)), DIST_DIR)


def ensure_directory_exists(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
