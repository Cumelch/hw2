import base64
import boto3
import os

def handler(event, context):
    client = boto3.client("s3", aws_access_key_id=os.getenv("aws_access_key"), aws_secret_access_key=os.getenv("aws_secret_key"), region_name="ru-central1", endpoint_url="https://storage.yandexcloud.net")
    
    params = event.get("queryStringParameters", {})
    face = params.get("face", "")
    photo = params.get("photo", "")
    
    if face != "":
        try:
            response = client.get_object(Bucket="vvot15-faces", Key=face)
            return {
                "isBase64Encoded": True,
                "statusCode": 200,
                "headers": {
                    "Content-Type": "image/jpeg"
                },
                "body": base64.b64encode(response["Body"].read()).decode("utf-8")
            }
        except FileNotFoundError:
            return {"statusCode": 500, "body": "Internal server error"}
    elif photo != "":
        try:
            response = client.get_object(Bucket="vvot15-photos", Key=photo)
            return {
                "isBase64Encoded": True,
                "statusCode": 200,
                "headers": {
                    "Content-Type": "image/jpeg"
                },
                "body": base64.b64encode(response["Body"].read()).decode("utf-8")
            }
        except:
            return {"statusCode": 500, "body": "Internal server error"}
    else:
        return {"statusCode": 500, "body": "Internal server error"}