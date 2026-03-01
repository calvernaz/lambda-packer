from pathlib import Path

from lambda_packer.builders.buildkit import BuildKitBuilder


def test_buildkit_push_image_disables_provenance_and_sbom(mocker, tmp_path):
    run = mocker.patch("lambda_packer.builders.buildkit.subprocess.run")

    builder = BuildKitBuilder()
    builder.build(
        dockerfile_content="FROM scratch\n",
        context_path=tmp_path,
        platforms=["linux/amd64"],
        output_type="image",
        tags=["example.com/app:latest"],
        push=True,
    )

    cmd = run.call_args.args[0]
    assert "--provenance=false" in cmd
    assert "--sbom=false" in cmd
    assert "--push" in cmd
    assert "type=image" in cmd


def test_buildkit_local_image_load_does_not_add_push_only_flags(mocker, tmp_path):
    run = mocker.patch("lambda_packer.builders.buildkit.subprocess.run")

    builder = BuildKitBuilder()
    builder.build(
        dockerfile_content="FROM scratch\n",
        context_path=tmp_path,
        platforms=["linux/amd64"],
        output_type="image",
        tags=["example.com/app:latest"],
        push=False,
    )

    cmd = run.call_args.args[0]
    assert "--load" in cmd
    assert "--provenance=false" not in cmd
    assert "--sbom=false" not in cmd
