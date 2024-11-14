from lambda_packer.config import Config
from lambda_packer.template_utils import (
    generate_lambda_handler,
    generate_package_config,
)


def test_generate_lambda_handler():
    lambda_name = "test_lambda"
    expected_output = """def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello from test_lambda!'
    }
"""
    assert generate_lambda_handler(lambda_name) == expected_output


def test_generate_package_config():
    lambda_name = "test_lambda"
    expected_output = f"""lambdas:
  test_lambda:
    type:
    - zip
    file_name: lambda
    function_name: lambda_handler
    runtime: '{Config.default_python_runtime}'
    platforms: {Config.default_platforms}
    layers:
      - common
"""
    assert generate_package_config(lambda_name) == expected_output
