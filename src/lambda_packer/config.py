"""Configuration schema for lambda-packer using Pydantic."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    """Supported output formats for Lambda functions."""

    ZIP = "zip"
    IMAGE = "image"


class LayerConfig(BaseModel):
    """Configuration for an AWS Lambda Layer."""

    path: Path
    """Root directory containing the layer source code."""

    runtime: Optional[str] = None
    """Python runtime version (e.g., 'python3.12'). Defaults to PackageConfig.runtime_default."""

    requirements: Optional[Path] = None
    """Path to a requirements.txt file specifically for this layer."""

    platforms: List[str] = Field(default_factory=lambda: ["linux/amd64"])
    """Target architectures for the layer."""


class LambdaConfig(BaseModel):
    """Configuration for an AWS Lambda Function."""

    path: Path
    """Root directory containing the Lambda handler and source code."""

    type: ArtifactType
    """The desired output format: 'zip' or 'image'."""

    runtime: Optional[str] = None
    """Python runtime version. Defaults to PackageConfig.runtime_default."""

    requirements: Optional[Path] = None
    """Path to a requirements.txt file for the Lambda's dependencies."""

    layers: List[str] = Field(default_factory=list)
    """List of layer names (defined in the 'layers' section) to include."""

    platforms: List[str] = Field(default_factory=lambda: ["linux/amd64"])
    """Target architectures for the Lambda."""

    image_tag: Optional[str] = None
    """Custom OCI tag for 'image' type. Supports {arch} and {name} placeholders."""

    handler: Optional[str] = None
    """The Lambda handler entry point (e.g., 'lambda_function.handler'). Required for 'image' type."""


class PackageConfig(BaseModel):
    """Root configuration object for a lambda-packer project."""

    runtime_default: str = "python3.12"
    """Global default Python runtime."""

    layers: Dict[str, LayerConfig] = Field(default_factory=dict)
    """Map of layer names to their configurations."""

    lambdas: Dict[str, LambdaConfig] = Field(default_factory=dict)
    """Map of lambda names to their configurations."""

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> PackageConfig:
        """Loads and validates a PackageConfig from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
