"""Wrapper for executing BuildKit builds via the Docker CLI."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional


class BuildKitBuilder:
    """Interfaces with 'docker buildx' to execute the generated build graph."""

    def __init__(self, buildx_instance: Optional[str] = None):
        self.buildx_instance = buildx_instance

    def build(
        self,
        dockerfile_content: str,
        context_path: Path,
        platforms: List[str],
        output_type: str = "local",
        output_dest: Optional[Path] = None,
        tags: Optional[List[str]] = None,
        cache_to: Optional[str] = None,
        cache_from: Optional[str] = None,
        push: bool = False,
    ) -> None:
        """
        Executes a BuildKit build.
        
        This method writes a temporary Dockerfile and calls 'docker buildx build'.
        It handles the logic for exporting to a local directory or loading into Docker.
        """

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".Dockerfile"
        ) as tmp_df:
            tmp_df.write(dockerfile_content)
            tmp_df_path = Path(tmp_df.name)

        try:
            cmd = ["docker", "buildx", "build"]

            if self.buildx_instance:
                cmd += ["--builder", self.buildx_instance]

            cmd += ["--platform", ",".join(platforms)]
            cmd += ["-f", str(tmp_df_path)]

            if output_type == "local":
                # Used for ZIP exports: produces a directory on the host.
                if not output_dest:
                    raise ValueError("output_dest is required for output_type='local'")
                cmd += ["--output", f"type=local,dest={output_dest}"]
            elif output_type == "image":
                if push:
                    # Push directly to the registry.
                    cmd += ["--output", "type=image"]
                    cmd += ["--push"]
                else:
                    # If building locally, we attempt to LOAD into the local Docker daemon
                    # so that 'docker run' works immediately.
                    # Note: --load only works for single-platform builds.
                    if len(platforms) <= 1:
                        cmd += ["--load"]
                    else:
                        print(
                            "Warning: Multi-platform build without --push cannot be "
                            "loaded into Docker daemon. Use --push to send to a registry."
                        )
                        cmd += ["--output", "type=image"]

                if tags:
                    for tag in tags:
                        cmd += ["-t", tag]

            # Support for BuildKit's powerful caching backends (local, registry, gha).
            if cache_to:
                cmd += ["--cache-to", cache_to]
            if cache_from:
                cmd += ["--cache-from", cache_from]

            cmd.append(str(context_path))

            print(f"Executing: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

        finally:
            # Cleanup the temporary Dockerfile.
            if tmp_df_path.exists():
                tmp_df_path.unlink()
