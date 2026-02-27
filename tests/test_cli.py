import pytest
from click.testing import CliRunner
from lambda_packer.cli import cli
from pathlib import Path
import yaml

def test_cli_build_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "--help"])
    assert result.exit_code == 0
    assert "Builds AWS Lambda and Layer artifacts defined in the configuration" in result.output

def test_cli_build_basic(tmp_path, mocker):
    runner = CliRunner()
    
    # Create a basic config
    config_content = {
        "runtime_default": "python3.12",
        "lambdas": {
            "api": {
                "path": str(tmp_path / "api"),
                "type": "zip",
            }
        }
    }
    
    config_path = tmp_path / "package_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_content, f)
        
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "main.py").write_text("def handler(): pass")
    
    # Mock the actual build process to avoid running docker
    mock_process = mocker.patch("lambda_packer.cli.process_target_platform")
    
    result = runner.invoke(cli, ["build", "--config", str(config_path), "--dist", str(tmp_path / "dist")])
    
    assert result.exit_code == 0
    assert "Found 1 build tasks" in result.output
    assert "Build complete!" in result.output
    
    mock_process.assert_called_once()
    
    # Check that manifest was generated
    manifest_path = tmp_path / "dist" / "build_manifest.json"
    assert manifest_path.exists()
