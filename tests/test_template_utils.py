import pytest
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
    expected_output = """lambdas:
  test_lambda:
    type:
    - zip
    layers:
      - common
"""
    assert generate_package_config(lambda_name) == expected_output
