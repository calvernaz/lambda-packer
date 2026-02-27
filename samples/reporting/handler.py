from utils import get_version

def handler(event, context):
    print(f"Reporting Version: {get_version()}")
    return {"statusCode": 200, "body": "Reporting Success"}
