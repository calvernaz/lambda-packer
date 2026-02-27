import pytest
import yaml
from pathlib import Path
from lambda_packer.config import PackageConfig, ArtifactType, LambdaConfig, LayerConfig

def test_package_config_parsing(tmp_path):
    config_content = """
    runtime_default: "python3.11"
    layers:
      common:
        path: ./layers/common
        runtime: "python3.11"
    lambdas:
      api:
        path: ./lambdas/api
        type: zip
        layers: [common]
        platforms: [linux/arm64]
      processor:
        path: ./lambdas/processor
        type: image
        handler: "app.handler"
    """
    config_path = tmp_path / "package_config.yaml"
    config_path.write_text(config_content)
    
    config = PackageConfig.from_yaml(config_path)
    
    assert config.runtime_default == "python3.11"
    assert "common" in config.layers
    assert config.layers["common"].path == Path("./layers/common")
    assert config.layers["common"].runtime == "python3.11"
    
    assert "api" in config.lambdas
    assert config.lambdas["api"].type == ArtifactType.ZIP
    assert config.lambdas["api"].layers == ["common"]
    assert config.lambdas["api"].platforms == ["linux/arm64"]
    
    assert "processor" in config.lambdas
    assert config.lambdas["processor"].type == ArtifactType.IMAGE
    assert config.lambdas["processor"].handler == "app.handler"
    assert config.lambdas["processor"].platforms == ["linux/amd64"] # Default

def test_config_invalid_type(tmp_path):
    config_content = """
    lambdas:
      api:
        path: ./lambdas/api
        type: invalid_type
    """
    config_path = tmp_path / "invalid_config.yaml"
    config_path.write_text(config_content)
    
    with pytest.raises(Exception): # Pydantic ValidationError
        PackageConfig.from_yaml(config_path)
