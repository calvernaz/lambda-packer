"""The Planner transforms the user configuration into a list of atomic BuildTargets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .config import ArtifactType, PackageConfig


@dataclass(frozen=True)
class BuildTarget:
    """
    Represents an atomic build task for a specific component and platform.
    This is the Intermediate Representation (IR) used by the Builders and Exporters.
    """

    name: str
    type: str  # "lambda" or "layer"
    artifact_format: ArtifactType
    path: Path
    runtime: str
    platforms: List[str]
    requirements: Optional[Path] = None
    layers: List[str] = field(default_factory=list)
    image_tag: Optional[str] = None
    handler: Optional[str] = None
    digest: Optional[str] = None


class Planner:
    """Orchestrates the resolution of dependencies and creation of build targets."""

    def __init__(self, config: PackageConfig):
        self.config = config

    def plan(self) -> List[BuildTarget]:
        """
        Flattens the configuration into a list of BuildTargets.
        Currently, this creates a Target for every component defined in the config.
        """
        targets = []

        # 1. Plan layers
        # Layers are built independently so they can be exported as standalone ZIPs
        for name, layer_config in self.config.layers.items():
            targets.append(
                BuildTarget(
                    name=name,
                    type="layer",
                    artifact_format=ArtifactType.ZIP,
                    path=layer_config.path,
                    runtime=layer_config.runtime or self.config.runtime_default,
                    platforms=layer_config.platforms,
                    requirements=layer_config.requirements,
                )
            )

        # 2. Plan lambdas
        for name, lambda_config in self.config.lambdas.items():
            targets.append(
                BuildTarget(
                    name=name,
                    type="lambda",
                    artifact_format=lambda_config.type,
                    path=lambda_config.path,
                    runtime=lambda_config.runtime or self.config.runtime_default,
                    platforms=lambda_config.platforms,
                    requirements=lambda_config.requirements,
                    layers=lambda_config.layers,
                    image_tag=lambda_config.image_tag,
                    handler=lambda_config.handler,
                )
            )

        return targets

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """Returns a graph of layer dependencies for each lambda."""
        graph = {}
        for name, lambda_cfg in self.config.lambdas.items():
            graph[name] = set(lambda_cfg.layers)
        return graph
