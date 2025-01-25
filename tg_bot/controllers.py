import os
import json
import telebot
import ydb

bot = telebot.TeleBot(os.getenv("tg_bot_key"))

@bot.message_handler(commands=["getface"])
def answer_getface(message):
    result = None

    driver_config = ydb.DriverConfig(endpoint=os.getenv("db_path").split("/?database=")[0], database=os.getenv("db_path").split("/?database=")[1], credentials=ydb.iam.MetadataUrlCredentials())
    driver = ydb.Driver(driver_config)
    driver.wait(30)
    session = driver.table_client.session().create()

    query = """
        SELECT pf.face_path AS face_path
        FROM photo_face AS pf
        WHERE pf.name IS NULL
        LIMIT 1;
    """

    result = session.transaction().execute(query, commit_tx=True)
    driver.stop()
        
    if result:
        try:
            photo_url = f"https://{os.getenv('gateway_domain')}?face={result[0].rows[0]['face_path'].decode('utf-8')}"
            bot.send_photo(message.chat.id, photo=photo_url, reply_to_message_id=message.message_id)
        except:
            bot.reply_to(message, "Нет доступных лиц без имени.")
    else:
        bot.reply_to(message, "Нет доступных лиц без имени.")

@bot.message_handler(commands=["find"])
def answer_find(message):
    name = message.text.split()[1]
    results = None

    driver_config = ydb.DriverConfig(endpoint=os.getenv("db_path").split("/?database=")[0], database=os.getenv("db_path").split("/?database=")[1], credentials=ydb.iam.MetadataUrlCredentials())
    driver = ydb.Driver(driver_config)
    driver.wait(30)
    session = driver.table_client.session().create()

    query = f"""
        DECLARE $face_name AS Utf8;

        SELECT pf.photo_path AS photo_path
        FROM photo_face AS pf
        WHERE pf.name = $face_name;
    """
    prepared_query = session.prepare(query)
    parameters = {"$face_name": name}
    results = session.transaction().execute(query=prepared_query, parameters=parameters, commit_tx=True)
    driver.stop()

    if results and results[0].rows != []:
        for row in results[0].rows:
            try:
                photo_url = f"https://{os.getenv('gateway_domain')}?photo={row['photo_path'].decode('utf-8')}"
                bot.send_photo(message.chat.id, photo=photo_url, reply_to_message_id=message.message_id)
            except:
                bot.reply_to(message, f"Фотографии с {name} не найдены.")
    else:
        bot.reply_to(message, f"Фотографии с {name} не найдены.")

@bot.message_handler(func=lambda message: True, content_types=["text","audio","voice","video","document","location","contact","sticker"])
def answer_other(message):
    if message.reply_to_message:
        if message.reply_to_message.photo:
            driver_config = ydb.DriverConfig(endpoint=os.getenv("db_path").split("/?database=")[0], database=os.getenv("db_path").split("/?database=")[1], credentials=ydb.iam.MetadataUrlCredentials())
            driver = ydb.Driver(driver_config)
            driver.wait(30)
            session = driver.table_client.session().create()

            query = """
                SELECT pf.face_path AS face_path
                FROM photo_face AS pf
                WHERE pf.name IS NULL
                LIMIT 1;
            """
            result = session.transaction().execute(query, commit_tx=True)
            if result:
                query = f"""
                    DECLARE $face_name AS Utf8;
                    DECLARE $face_photo_name AS Utf8;

                    UPDATE photo_face
                    SET name = $face_name
                    WHERE face_path = $face_photo_name;
                """
                prepared_query = session.prepare(query)
                parameters = {"$face_photo_name": result[0].rows[0]['face_path'].decode('utf-8'), "$face_name": message.text}
                session.transaction().execute(query=prepared_query, parameters=parameters, commit_tx=True)
                driver.stop()
            else:
                bot.reply_to(message, "Ошибка")
        else:
            bot.reply_to(message, "Ошибка")
    else:
        bot.reply_to(message, "Ошибка")

def handler(event, context):
    if event.get("httpMethod") == "POST":
        body = event.get("body")

        try:
            update_data = json.loads(body)
            update = telebot.types.Update.de_json(update_data)
            bot.process_new_updates([update])
            return {"statusCode": 200, "body": "OK"}
        except:
            return {"statusCode": 500, "body": "Internal server error"}