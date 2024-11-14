import os
from tempfile import TemporaryDirectory

import yaml
from lambda_packer.file_utils import (
    get_common_paths,
    read_yaml,
    write_yaml,
    file_exists,
    abs_to_rel_path,
    create_file,
    config_file_path,
    dist_dir_path,
)


def test_get_common_paths():
    parent_dir = "test_parent"
    lambda_name = "test_lambda"
    parent_path, common_dir, lambda_dir, dist_dir, package_config_path = (
        get_common_paths(parent_dir, lambda_name)
    )

    assert parent_path.endswith(parent_dir)
    assert common_dir.endswith(os.path.join(parent_dir, "common"))
    assert lambda_dir.endswith(os.path.join(parent_dir, lambda_name))
    assert dist_dir.endswith(os.path.join(parent_dir, "dist"))
    assert package_config_path.endswith(os.path.join(parent_dir, "package_config.yaml"))


def test_read_yaml():
    with TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "test.yaml")
        data = {"key": "value"}
        with open(file_path, "w") as file:
            yaml.dump(data, file)

        result = read_yaml(file_path)
        assert result == data


def test_write_yaml():
    with TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "test.yaml")
        data = {"key": "value"}

        write_yaml(file_path, data)

        with open(file_path, "r") as file:
            result = yaml.safe_load(file)

        assert result == data


def test_file_exists():
    with TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "test.txt")
        with open(file_path, "w") as file:
            file.write("test")

        assert file_exists(file_path)
        assert not file_exists(os.path.join(temp_dir, "non_existent.txt"))


def test_abs_to_rel_path():
    abs_path = os.path.abspath(__file__)
    rel_path = abs_to_rel_path(abs_path)

    assert os.path.isabs(abs_path)
    assert not os.path.isabs(rel_path)


def test_create_file():
    with TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "test.txt")
        content = "test content"

        create_file(file_path, content)

        with open(file_path, "r") as file:
            result = file.read()

        assert result == content


def test_config_file_path():
    repo = "/test/repo"
    result = config_file_path(repo)

    assert result == os.path.join(repo, "package_config.yaml")


def test_dist_dir_path():
    repo = "/test/repo"
    result = dist_dir_path(repo)

    assert result == os.path.join(repo, "dist")
