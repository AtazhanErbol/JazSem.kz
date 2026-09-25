import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the private development bucket; never run in production."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Development storage initialization is disabled in production")
        storage = settings.STORAGES["default"].get("OPTIONS", {})
        if not storage.get("endpoint_url") or not storage.get("bucket_name"):
            raise CommandError("Configure a development S3 endpoint and bucket")
        client = boto3.client(
            "s3",
            endpoint_url=storage["endpoint_url"],
            aws_access_key_id=storage["access_key"],
            aws_secret_access_key=storage["secret_key"],
            region_name=storage["region_name"],
        )
        for attempt in range(30):
            try:
                try:
                    client.head_bucket(Bucket=storage["bucket_name"])
                except ClientError as exc:
                    if exc.response["Error"]["Code"] not in ["404", "NoSuchBucket"]:
                        raise
                    client.create_bucket(Bucket=storage["bucket_name"])
                self.stdout.write("Private development bucket ready")
                return
            except (BotoCoreError, ClientError):
                if attempt == 29:
                    raise CommandError(
                        "Development S3 is unavailable; check configuration"
                    ) from None
                time.sleep(2)
