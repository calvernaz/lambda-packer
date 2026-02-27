from utils import get_version

def handler(event, context):
    print(f"Billing Version: {get_version()}")
    return {"statusCode": 200, "body": "Billing Success"}
