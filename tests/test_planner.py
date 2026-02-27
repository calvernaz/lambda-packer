import pytest
from pathlib import Path
from lambda_packer.config import PackageConfig, ArtifactType, LambdaConfig, LayerConfig
from lambda_packer.planner import Planner

def test_planner_creates_targets():
    config = PackageConfig(
        runtime_default="python3.12",
        layers={
            "common-utils": LayerConfig(path=Path("common"), runtime="python3.10")
        },
        lambdas={
            "api": LambdaConfig(
                path=Path("api"),
                type=ArtifactType.ZIP,
                layers=["common-utils"]
            ),
            "web": LambdaConfig(
                path=Path("web"),
                type=ArtifactType.IMAGE,
                handler="main.handler"
            )
        }
    )
    
    planner = Planner(config)
    targets = planner.plan()
    
    assert len(targets) == 3
    
    layer_target = next(t for t in targets if t.name == "common-utils")
    assert layer_target.type == "layer"
    assert layer_target.runtime == "python3.10"
    assert layer_target.artifact_format == ArtifactType.ZIP
    
    api_target = next(t for t in targets if t.name == "api")
    assert api_target.type == "lambda"
    assert api_target.runtime == "python3.12" # Fallback to default
    assert api_target.layers == ["common-utils"]
    assert api_target.artifact_format == ArtifactType.ZIP
    
    web_target = next(t for t in targets if t.name == "web")
    assert web_target.type == "lambda"
    assert web_target.runtime == "python3.12"
    assert web_target.artifact_format == ArtifactType.IMAGE
    assert web_target.handler == "main.handler"

def test_planner_dependency_graph():
    config = PackageConfig(
        lambdas={
            "api": LambdaConfig(path=Path("api"), type=ArtifactType.ZIP, layers=["layer1", "layer2"]),
            "web": LambdaConfig(path=Path("web"), type=ArtifactType.ZIP)
        }
    )
    
    planner = Planner(config)
    graph = planner.get_dependency_graph()
    
    assert graph == {
        "api": {"layer1", "layer2"},
        "web": set()
    }
