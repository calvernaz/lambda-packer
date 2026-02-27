"""OCI Image tagging and registry export policies."""

from __future__ import annotations

from typing import List, Optional


class OCIExporter:
    """
    Handles the naming and tagging strategy for OCI images.
    
    This ensures consistency across different architectures and registries.
    """

    def __init__(self, default_registry: str = "lambda-packer"):
        self.default_registry = default_registry

    def resolve_tag(
        self,
        name: str,
        arch: str,
        custom_tag: Optional[str] = None,
    ) -> str:
        """
        Resolves the final OCI tag for a target.
        
        Supports placeholders:
        - {name}: The name of the lambda.
        - {arch}: The architecture (e.g., amd64, arm64).
        """
        if custom_tag:
            return custom_tag.format(name=name, arch=arch)
        
        return f"{self.default_registry}/{name}:{arch}"

    def get_export_args(self, tags: List[str], push: bool = False) -> dict:
        """
        Returns BuildKit export arguments for an OCI image.
        """
        return {
            "output_type": "image",
            "tags": tags,
            "push": push,
        }
