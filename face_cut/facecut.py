import boto3
import os
import json
import random
import ydb
from PIL import Image
from io import BytesIO

def handler(event, context):

    client = boto3.client("s3", aws_access_key_id=os.getenv("aws_access_key"), aws_secret_access_key=os.getenv("aws_secret_key"), region_name="ru-central1", endpoint_url="https://storage.yandexcloud.net")

    driver_config = ydb.DriverConfig(endpoint=os.getenv("db_path").split("/?database=")[0], database=os.getenv("db_path").split("/?database=")[1], credentials=ydb.iam.MetadataUrlCredentials())
    driver = ydb.Driver(driver_config)

    for record in event["messages"]:
        task = json.loads(record["details"]["message"]["body"])
        photo_name = task["photo_name"]
        left, top, right, bottom = task["coordinates"]

        response = client.get_object(Bucket="vvot15-photos", Key=photo_name)
        with open(f"/tmp/{photo_name}", "wb") as f:
            f.write(response["Body"].read())

        image = Image.open(f"/tmp/{photo_name}")
        cut_face = image.crop((left, top, right, bottom))

        face_photo_name = f"{photo_name}_{random.randint(1000, 1000000)}.jpg"
        with BytesIO() as buffer:
            cut_face.save(buffer, format="JPEG")
            buffer.seek(0) 
            client.put_object(Bucket="vvot15-faces", Key=face_photo_name, Body=buffer, ContentType='image/jpeg')
        
        session = driver.table_client.session().create()
        query = f"""
            DECLARE $face_photo_name AS Utf8;
            DECLARE $photo_name AS Utf8;

            INSERT INTO photo_face (face_path, photo_path)
            VALUES ($face_photo_name, $photo_name);
        """
        prepared_query = session.prepare(query)
        parameters = {"$face_photo_name": face_photo_name, "$photo_name": photo_name}
        session.transaction().execute(query=prepared_query, parameters=parameters, commit_tx=True)
        driver.stop()

    return {"statusCode": 200, "body": "OK"}