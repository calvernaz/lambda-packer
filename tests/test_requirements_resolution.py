from pathlib import Path

from lambda_packer.cli import process_target_platform
from lambda_packer.config import ArtifactType, LayerConfig, PackageConfig
from lambda_packer.planner import BuildTarget


def test_process_target_platform_uses_local_lambda_requirements_by_default(
    mocker, tmp_path
):
    lambda_dir = tmp_path / "lambda"
    lambda_dir.mkdir()
    (lambda_dir / "lambda_function.py").write_text("def handler(event, context): return 1\n")
    (lambda_dir / "requirements.txt").write_text("requests==2.32.0\n")

    target = BuildTarget(
        name="api",
        type="lambda",
        artifact_format=ArtifactType.IMAGE,
        path=lambda_dir,
        runtime="python3.12",
        platforms=["linux/amd64"],
        handler="lambda_function.handler",
    )

    pkg_cfg = PackageConfig()
    builder = mocker.Mock()
    oci_exporter = mocker.Mock()
    oci_exporter.resolve_tag.return_value = "example.com/api:amd64"
    oci_exporter.get_export_args.return_value = {
        "output_type": "image",
        "tags": ["example.com/api:amd64"],
        "push": True,
    }
    manifest = mocker.Mock()

    process_target_platform(
        target=target,
        platform="linux/amd64",
        pkg_cfg=pkg_cfg,
        dist=tmp_path / "dist",
        cache=None,
        push=True,
        df_gen=mocker.Mock(generate=mocker.Mock(return_value="COPY requirements.txt /tmp/requirements.txt")),
        builder=builder,
        zip_exporter=mocker.Mock(),
        oci_exporter=oci_exporter,
        manifest=manifest,
    )

    builder.build.assert_called_once()
    assert "requirements.txt" in builder.build.call_args.kwargs["dockerfile_content"]


def test_process_target_platform_uses_local_layer_requirements_by_default(
    mocker, tmp_path
):
    lambda_dir = tmp_path / "lambda"
    lambda_dir.mkdir()
    (lambda_dir / "lambda_function.py").write_text("def handler(event, context): return 1\n")

    layer_dir = tmp_path / "layer"
    layer_dir.mkdir()
    (layer_dir / "helper.py").write_text("VALUE = 1\n")
    (layer_dir / "requirements.txt").write_text("requests==2.32.0\n")

    target = BuildTarget(
        name="api",
        type="lambda",
        artifact_format=ArtifactType.IMAGE,
        path=lambda_dir,
        runtime="python3.12",
        platforms=["linux/amd64"],
        layers=["common"],
        handler="lambda_function.handler",
    )

    pkg_cfg = PackageConfig(layers={"common": LayerConfig(path=layer_dir)})
    builder = mocker.Mock()
    oci_exporter = mocker.Mock()
    oci_exporter.resolve_tag.return_value = "example.com/api:amd64"
    oci_exporter.get_export_args.return_value = {
        "output_type": "image",
        "tags": ["example.com/api:amd64"],
        "push": True,
    }
    manifest = mocker.Mock()

    df_gen = mocker.Mock()
    df_gen.generate.return_value = "COPY layer_common_requirements.txt /tmp/requirements.txt"

    process_target_platform(
        target=target,
        platform="linux/amd64",
        pkg_cfg=pkg_cfg,
        dist=tmp_path / "dist",
        cache=None,
        push=True,
        df_gen=df_gen,
        builder=builder,
        zip_exporter=mocker.Mock(),
        oci_exporter=oci_exporter,
        manifest=manifest,
    )

    builder.build.assert_called_once()
    assert "layer_common_requirements.txt" in builder.build.call_args.kwargs["dockerfile_content"]
