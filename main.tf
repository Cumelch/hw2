terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

variable "cloud_id" {
  type = string
}

variable "folder_id" {
  type = string
}

variable "tg_bot_key" {
  type = string
}

variable "iam_token" {
  type = string
}

provider "yandex" {
  cloud_id = var.cloud_id
  folder_id = var.folder_id
  service_account_key_file = "/Users/cumelch/keys/yc-key.json"
}

resource "yandex_iam_service_account" "telegram-bot-kamilla" {
  name = "telegram-bot-kamilla"
  folder_id = var.folder_id
}

resource "yandex_iam_service_account_static_access_key" "aws" {
  service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id
}

resource "archive_file" "zip" {
  type = "zip"
  output_path = "tg_bot.zip"
  source_dir = "tg_bot"
}

resource "archive_file" "face_detection" {
  type = "zip"
  output_path = "face_detection.zip"
  source_dir = "face_detection"
}

resource "archive_file" "face_cut" {
  type = "zip"
  output_path = "face_cut.zip"
  source_dir = "face_cut"
}

resource "archive_file" "api_gw" {
  type = "zip"
  output_path = "api_gw.zip"
  source_dir = "api_gw"
}

resource "yandex_storage_bucket" "photos-bucket" {
  bucket = "vvot15-photos"
  folder_id = var.folder_id
}

resource "yandex_storage_bucket" "faces-bucket" {
  bucket = "vvot15-faces"
  folder_id = var.folder_id
}

resource "yandex_resourcemanager_folder_iam_binding" "storage-bind" {
  folder_id = var.folder_id
  role = "editor"

  members = [
    "serviceAccount:${yandex_iam_service_account.telegram-bot-kamilla.id}",
  ]
}

resource "yandex_function_iam_binding" "func-invoker-bind" {
  function_id = yandex_function.func.id
  role = "serverless.functions.invoker"

  members = [
    "serviceAccount:${yandex_iam_service_account.telegram-bot-kamilla.id}",
  ]
}

resource "yandex_function" "func" {
  name = "vvot15-boot"
  user_hash = archive_file.zip.output_sha256
  runtime = "python312"
  entrypoint = "controllers.handler"
  memory = 128
  execution_timeout = 300
  service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id

  environment = {
    "tg_bot_key" = var.tg_bot_key
    "iam_token" = var.iam_token
    "folder_id" = var.folder_id
    "cloud_id" = var.cloud_id
    "db_path" = yandex_ydb_database_serverless.db-photo-face.ydb_full_endpoint
    "gateway_domain" = yandex_api_gateway.api-gateway.domain
  }

  content {
    zip_filename = archive_file.zip.output_path
  }
}

resource "yandex_function" "func-face-detection" {
  name = "vvot15-face-detection"
  user_hash = archive_file.face_detection.output_sha256
  runtime = "python312"
  entrypoint = "facedetection.handler"
  memory = 128
  execution_timeout = 300
  service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id

  environment = {
    "queue_id" = yandex_message_queue.queue.id
    "aws_access_key" = yandex_iam_service_account_static_access_key.aws.access_key
    "aws_secret_key" = yandex_iam_service_account_static_access_key.aws.secret_key
  }

  content {
    zip_filename = archive_file.face_detection.output_path
  }
}

resource "yandex_function" "func-face-cut" {
  name = "vvot15-face-cut"
  user_hash = archive_file.face_cut.output_sha256
  runtime = "python312"
  entrypoint = "facecut.handler"
  memory = 128
  execution_timeout = 300
  service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id

  environment = {
    "aws_access_key" = yandex_iam_service_account_static_access_key.aws.access_key
    "aws_secret_key" = yandex_iam_service_account_static_access_key.aws.secret_key
    "db_path" = yandex_ydb_database_serverless.db-photo-face.ydb_full_endpoint
  }

  content {
    zip_filename = archive_file.face_cut.output_path
  }
}

resource "yandex_function" "func-api-gw" {
  name = "vvot15-apigw"
  user_hash = archive_file.api_gw.output_sha256
  runtime = "python312"
  entrypoint = "apigw.handler"
  memory = 128
  execution_timeout = 300
  service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id

  environment = {
    "aws_access_key" = yandex_iam_service_account_static_access_key.aws.access_key
    "aws_secret_key" = yandex_iam_service_account_static_access_key.aws.secret_key
  }

  content {
    zip_filename = archive_file.api_gw.output_path
  }
}

resource "yandex_message_queue" "queue" {
  name = "vvot15-task"
  visibility_timeout_seconds = 60
  receive_wait_time_seconds = 20
  message_retention_seconds = 60
  access_key = yandex_iam_service_account_static_access_key.aws.access_key
  secret_key = yandex_iam_service_account_static_access_key.aws.secret_key
}

resource "yandex_function_trigger" "upload-trigger" {
  name = "vvot15-photos"
  
  object_storage {
    bucket_id = yandex_storage_bucket.photos-bucket.id
    suffix = ".jpg"
    create = true
    update = false
    delete = false
    batch_cutoff = 5
  }

  function {
    id = yandex_function.func-face-detection.id
    service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id
  }
}

resource "yandex_function_trigger" "cut-trigger" {
  name = "vvot15-task"

  message_queue {
    queue_id = yandex_message_queue.queue.arn
    service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id
    batch_cutoff = "5"
    batch_size = "5"
  }
  function {
    id = yandex_function.func-face-cut.id
    service_account_id = yandex_iam_service_account.telegram-bot-kamilla.id
  }
}

resource "yandex_ydb_database_serverless" "db-photo-face" {
  name = "vvot15-db-photo-face"
  deletion_protection = false

  serverless_database {
    enable_throttling_rcu_limit = false
    provisioned_rcu_limit = 10
    storage_size_limit = 1
    throttling_rcu_limit = 0
  }
}

resource "yandex_ydb_table" "table" {
  path = "photo_face"
  connection_string = yandex_ydb_database_serverless.db-photo-face.ydb_full_endpoint

  column {
    name = "face_path"
    type = "String"
    not_null = true
  }
  column {
    name = "photo_path"
    type = "String"
    not_null = true
  }
  column {
    name = "name"
    type = "String"
    not_null = false
  }

  primary_key = ["face_path"]
}

resource "yandex_api_gateway" "api-gateway" {
  name = "vvot15-apigw"
  spec = <<-EOT
    openapi: "3.0.0"
    info:
      version: 1.0.0
      title: api-gateway
    paths:
      /:
        get:
          parameters:
            - name: face
              in: query
              required: false
            - name: photo
              in: query
              required: false
          responses:
            "200":
              description: Result
              content:
                image/jpeg:
                  schema:
                    type: string
                    format: binary
          x-yc-apigateway-integration:
            type: cloud_functions
            payload_format_version: '0.1'
            function_id: ${yandex_function.func-api-gw.id}
            tag: $latest
            service_account_id: ${yandex_iam_service_account.telegram-bot-kamilla.id}
  EOT
}

resource "null_resource" "curl" {
  provisioner "local-exec" {
    command = "curl --insecure -X POST https://api.telegram.org/bot${var.tg_bot_key}/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.func.id}"
  }

  triggers = {
    tg_bot_key = var.tg_bot_key
  }

  provisioner "local-exec" {
    when = destroy
    command = "curl --insecure -X POST https://api.telegram.org/bot${self.triggers.tg_bot_key}/deleteWebhook"
  }
}