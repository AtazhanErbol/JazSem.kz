"""One-time/idempotent Vercel build preparation, without loading web settings."""

import hashlib
import os
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit, urlunsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from config.ocr_assets import COMMIT, MODELS, PREFIX
from config.vercel_environment import configure_preview, configure_storage


def initialize_models(client, bucket):
    for language, (digest, size) in MODELS.items():
        key = f"{PREFIX}/{language}.traineddata"
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
        except ClientError as error:
            if error.response["Error"]["Code"] not in {"NoSuchKey", "404"}:
                raise
        else:
            try:
                data = obj["Body"].read(size + 1)
            finally:
                obj["Body"].close()
            if len(data) == size and hashlib.sha256(data).hexdigest() == digest:
                continue
            raise RuntimeError("Existing OCR model failed integrity validation")
        url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{COMMIT}/{language}.traineddata"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(size + 1)
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError("Official OCR model failed integrity validation")
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType="application/octet-stream")


def verify_direct_upload(client, bucket, origin):
    size = 25 * 1024 * 1024
    key = "private/quarantine/deployment-check-" + uuid.uuid4().hex
    grant = client.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields={"Content-Type": "text/plain"},
        Conditions=[{"Content-Type": "text/plain"}, ["content-length-range", size, size]],
        ExpiresIn=300,
    )
    boundary = "JazSem" + uuid.uuid4().hex
    parts = []
    for name, value in grant["fields"].items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="check.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n".encode()
    )
    parts.extend([b"a" * size, f"\r\n--{boundary}--\r\n".encode()])
    try:
        request = urllib.request.Request(
            grant["url"],
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Origin": origin},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            cors = response.headers.get("Access-Control-Allow-Origin")
            print(
                "Upload CORS response: "
                + (
                    "credential-free wildcard"
                    if cors == "*"
                    else "exact origin"
                    if cors == origin
                    else "missing or unexpected"
                ),
                flush=True,
            )
            # Browser uploads deliberately omit cookies and HTTP credentials.
            # A provider's wildcard response is valid for these signed grants;
            # the object still requires its scoped signature and stays private.
            if cors not in {origin, "*"}:
                raise RuntimeError("Storage CORS verification failed")
        print("Direct POST and browser CORS verified.", flush=True)
        if client.head_object(Bucket=bucket, Key=key)["ContentLength"] != size:
            raise RuntimeError("25 MiB upload verification failed")
        print("Stored object size verified: 25 MiB.", flush=True)
        signed_url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentType": "application/octet-stream",
                "ResponseContentDisposition": 'attachment; filename="check.txt"',
            },
            ExpiresIn=60,
        )
        with urllib.request.urlopen(
            urllib.request.Request(signed_url, headers={"Range": "bytes=0-15"}), timeout=30
        ) as response:
            if response.read(17) != b"a" * 16:
                raise RuntimeError("Signed private download verification failed")
            if not response.headers.get("Content-Disposition", "").startswith("attachment;"):
                raise RuntimeError("Signed download attachment verification failed")
        print("Signed range download and attachment headers verified.", flush=True)
        signed = urlsplit(signed_url)
        anonymous = urlunsplit((signed.scheme, signed.netloc, signed.path, "", ""))
        try:
            with urllib.request.urlopen(anonymous, timeout=30):
                raise RuntimeError("Storage privacy verification failed")
        except urllib.error.HTTPError as error:
            if error.code not in {403, 404}:
                raise RuntimeError("Storage privacy verification was inconclusive") from None
    finally:
        client.delete_object(Bucket=bucket, Key=key)


def safe_error(error):
    """Never include signed URLs, provider messages, or credential values."""
    if isinstance(error, urllib.error.HTTPError):
        return f"Storage HTTP status {error.code}"
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code")
        known = {
            "AccessDenied",
            "NoSuchBucket",
            "NotImplemented",
            "InvalidArgument",
            "SignatureDoesNotMatch",
            "InvalidPolicyDocument",
        }
        return "Storage API error: " + (code if code in known else "provider_error")
    known = {
        "Storage CORS verification failed",
        "25 MiB upload verification failed",
        "Signed private download verification failed",
        "Signed download attachment verification failed",
        "Storage privacy verification failed",
        "Storage privacy verification was inconclusive",
        "Existing OCR model failed integrity validation",
        "Official OCR model failed integrity validation",
        "Invalid storage CORS origins",
    }
    if isinstance(error, RuntimeError) and str(error) in known:
        return str(error)
    return "Storage preparation failed: " + type(error).__name__


def main():
    if os.environ.get("VERCEL") != "1":
        raise RuntimeError("This setup command requires the Vercel deployment environment")
    configure_preview(os.environ)
    configure_storage(os.environ)
    origins = list(
        dict.fromkeys(
            [os.environ["FRONTEND_URL"].rstrip("/"), *os.environ["CSRF_TRUSTED_ORIGINS"].split(",")]
        )
    )
    allowed = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")
    if any(
        urlsplit(origin).scheme != "https"
        or urlsplit(origin).hostname not in allowed
        or urlsplit(origin).path not in {"", "/"}
        or urlsplit(origin).query
        or urlsplit(origin).username
        for origin in origins
    ):
        raise RuntimeError("Invalid storage CORS origins")
    # Both environments share this private bucket. Preserve both canonical
    # origins when their builds update CORS, without allowing wildcard origins.
    origins = sorted(set(origins + ["https://" + host for host in allowed]))
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        region_name=os.environ["S3_REGION"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=60),
    )
    bucket = os.environ["S3_BUCKET"]
    print("Configuring private storage CORS.", flush=True)
    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": origins,
                    "AllowedMethods": ["POST"],
                    "AllowedHeaders": ["Content-Type"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 300,
                }
            ]
        },
    )
    print("Initializing checksum-verified Russian, Kazakh and English OCR assets.", flush=True)
    initialize_models(client, bucket)
    print("Verifying a 25 MiB direct upload, browser CORS and private access.", flush=True)
    verify_direct_upload(client, bucket, origins[0])
    print("Storage initialized; 25 MiB direct upload and private access verified.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Provider exceptions and signed request URLs can contain credentials.
        raise SystemExit(safe_error(error)) from None
