import boto3
import os
import json
import cv2

def handler(event, context):
    client = boto3.client("s3", aws_access_key_id=os.getenv("aws_access_key"), aws_secret_access_key=os.getenv("aws_secret_key"), region_name="ru-central1", endpoint_url="https://storage.yandexcloud.net")
    queue = boto3.client("sqs", aws_access_key_id=os.getenv("aws_access_key"), aws_secret_access_key=os.getenv("aws_secret_key"), region_name="ru-central1", endpoint_url="https://message-queue.api.cloud.yandex.net")

    for record in event["messages"]:
        object_id = record["details"]["object_id"]
        response = client.get_object(Bucket="vvot15-photos", Key=object_id)

        with open(f"/tmp/{object_id}", "wb") as f:
            f.write(response["Body"].read())
            
        image = cv2.imread(f"/tmp/{object_id}")
        haar_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        classifier = cv2.CascadeClassifier(haar_cascade_path)
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        faces = classifier.detectMultiScale(image_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        coordinates = []
        for (x, y, w, h) in faces:
            coordinates = [int(x), int(y), int(x + w), int(y + h)]
            break

        task = {"photo_name": object_id, "coordinates": coordinates}
        queue.send_message(QueueUrl=os.getenv("queue_id"), MessageBody=json.dumps(task))

    return {"statusCode": 200, "body": "OK"}