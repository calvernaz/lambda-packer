"""Main CLI entry point for lambda-packer."""

from __future__ import annotations

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import click

from .builders.buildkit import BuildKitBuilder
from .builders.dockerfile_gen import DockerfileGenerator
from .config import ArtifactType, PackageConfig
from .dist_layout import ManifestGenerator
from .exporters.zip import ZipExporter
from .planner import Planner


@click.group()
def cli():
    """Lambda Packer: A BuildKit-native tool for AWS Lambda and Layers."""
    pass


def process_target_platform(
    target,
    platform,
    pkg_cfg,
    dist,
    cache,
    push,
    df_gen,
    builder,
    zip_exporter,
    manifest,
):
    """
    Orchestrates the build for a single target on a specific platform.
    
    This function implements the 'Standardized Staging' strategy:
    1. Creates a temporary context directory.
    2. Maps all files (src, requirements, layers) into fixed paths within the context.
    3. Triggers BuildKit.
    4. Handles the artifact export (ZIP or Image).
    """
    arch = platform.split("/")[-1]
    platform_dist = dist / target.name / arch
    platform_dist.mkdir(parents=True, exist_ok=True)

    print(f"Building {target.type} {target.name} ({platform})...")

    # 1. Prepare a clean build context.
    # We use a temporary directory to avoid sending unnecessary files to Docker
    # and to support absolute paths from external projects.
    with tempfile.TemporaryDirectory() as temp_context_dir:
        temp_context = Path(temp_context_dir)

        # Map Lambda source to 'src/'
        shutil.copytree(target.path, temp_context / "src", dirs_exist_ok=True)

        # Map requirements to 'requirements.txt'
        has_requirements = False
        if target.requirements:
            shutil.copy2(target.requirements, temp_context / "requirements.txt")
            has_requirements = True

        # Map Layers to 'layer_<name>/'
        layer_requirements_map = {}
        for layer_name in target.layers:
            layer_cfg = pkg_cfg.layers[layer_name]
            layer_dest = temp_context / f"layer_{layer_name}"
            shutil.copytree(layer_cfg.path, layer_dest, dirs_exist_ok=True)

            if layer_cfg.requirements:
                shutil.copy2(
                    layer_cfg.requirements,
                    temp_context / f"layer_{layer_name}_requirements.txt",
                )
                layer_requirements_map[layer_name] = True
            else:
                layer_requirements_map[layer_name] = False

        # 2. Generate the Dockerfile tailored for this standardized context.
        df_content = df_gen.generate(
            runtime=target.runtime,
            requirements=has_requirements,
            layers=target.layers,
            layer_requirements=layer_requirements_map,
            is_image=(target.artifact_format == ArtifactType.IMAGE),
            handler=target.handler,
        )

        # 3. Execute BuildKit build.
        if target.artifact_format == ArtifactType.ZIP:
            builder.build(
                dockerfile_content=df_content,
                context_path=temp_context,
                platforms=[platform],
                output_type="local",
                output_dest=platform_dist / "asset",
                cache_to=cache,
                cache_from=cache,
            )

            # For ZIP targets, we run the deterministic exporter on the resulting filesystem.
            zip_path = dist / f"{target.name}-{arch}.zip"
            zip_exporter.export(platform_dist / "asset", zip_path)
            manifest.add_artifact(
                target.name, target.type, zip_path, {"platform": platform}
            )

        elif target.artifact_format == ArtifactType.IMAGE:
            # For Image targets, we build and optionally push to a registry.
            tag = (
                target.image_tag.format(arch=arch, name=target.name)
                if target.image_tag
                else f"lambda-packer/{target.name}:{arch}"
            )
            builder.build(
                dockerfile_content=df_content,
                context_path=temp_context,
                platforms=[platform],
                output_type="image",
                tags=[tag],
                push=push,
                cache_to=cache,
                cache_from=cache,
            )
            manifest.add_artifact(target.name, target.type, tag, {"platform": platform})


@cli.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("package_config.yaml"),
    help="Path to the package config YAML.",
)
@click.option(
    "--dist",
    type=click.Path(path_type=Path),
    default=Path("dist"),
    help="Output directory for build artifacts.",
)
@click.option("--cache", type=str, help="BuildKit cache options.")
@click.option("--push", is_flag=True, help="Push image artifacts to registry.")
@click.option(
    "-j", "--concurrency", type=int, default=1, help="Number of parallel builds."
)
def build(config: Path, dist: Path, cache: Optional[str], push: bool, concurrency: int):
    """Builds AWS Lambda and Layer artifacts defined in the configuration."""
    pkg_cfg = PackageConfig.from_yaml(config)
    planner = Planner(pkg_cfg)
    targets = planner.plan()

    df_gen = DockerfileGenerator()
    builder = BuildKitBuilder()
    zip_exporter = ZipExporter()
    manifest = ManifestGenerator(dist)

    dist.mkdir(parents=True, exist_ok=True)

    # Gather all tasks (target + platform combinations)
    tasks = []
    for target in targets:
        for platform in target.platforms:
            tasks.append((target, platform))

    print(f"Found {len(tasks)} build tasks. Parallelism: {concurrency}")

    # Execute builds in parallel using a ThreadPoolExecutor.
    # Each task is an independent 'docker buildx' call.
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                process_target_platform,
                target,
                platform,
                pkg_cfg,
                dist,
                cache,
                push,
                df_gen,
                builder,
                zip_exporter,
                manifest,
            ): (target, platform)
            for target, platform in tasks
        }
        for future in as_completed(futures):
            target, platform = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Build failed for {target.name} ({platform}): {e}")

    # Record all results in the build_manifest.json
    manifest.save()
    print("\nBuild complete!")


if __name__ == "__main__":
    cli()
