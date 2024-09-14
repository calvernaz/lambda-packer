def generate_package_config(lambda_name):
    """Generate the content for package_config.yaml."""
    return f"""lambdas:
  {lambda_name}:
    type: zip
    layers:
      - common
"""


def generate_lambda_handler(lambda_name):
    """Generate the content for lambda_handler.py."""
    return f"""def lambda_handler(event, context):
    return {{
        'statusCode': 200,
        'body': 'Hello from {lambda_name}!'
    }}
"""
