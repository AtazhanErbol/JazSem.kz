"""Map provider-managed Vercel variables without copying credentials into code."""

import re


def configure_preview(env):
    """Use the provider's stable branch alias for each isolated preview database."""
    if env.get("VERCEL_ENV") != "preview":
        return
    host = env.get("VERCEL_BRANCH_URL", "")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.vercel\.app", host):
        raise RuntimeError("Invalid Vercel preview branch identity")
    origin = "https://" + host
    env["FRONTEND_URL"] = origin
    env["CSRF_TRUSTED_ORIGINS"] = origin
    hosts = [item.strip() for item in env.get("DJANGO_ALLOWED_HOSTS", "").split(",")]
    env["DJANGO_ALLOWED_HOSTS"] = ",".join(dict.fromkeys(item for item in [*hosts, host] if item))


def configure_storage(env):
    if not env.get("TIGRIS_STORAGE_BUCKET"):
        return
    mappings = {
        "S3_BUCKET": "TIGRIS_STORAGE_BUCKET",
        "S3_ACCESS_KEY": "TIGRIS_STORAGE_ACCESS_KEY_ID",
        "S3_SECRET_KEY": "TIGRIS_STORAGE_SECRET_ACCESS_KEY",
    }
    for target, source in mappings.items():
        if not env.get(target):
            if not env.get(source):
                raise RuntimeError(f"Missing integration setting: {source}")
            env[target] = env[source]
    env.setdefault("S3_ENDPOINT_URL", "https://t3.storage.dev")
    env.setdefault("S3_REGION", "auto")


def configure_runtime(env):
    if env.get("VERCEL") != "1":
        raise RuntimeError("The Vercel entrypoint requires the Vercel runtime")
    for key, value in {
        "TRUSTED_PROXY_CIDRS": "127.0.0.1/32",
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "BACKGROUND_MODE": "vercel",
        "OCR_ENGINE": "embedded",
        "DIRECT_UPLOADS_ENABLED": "true",
    }.items():
        if env.setdefault(key, value) != value:
            raise RuntimeError(f"Invalid Vercel runtime setting: {key}")
    configure_preview(env)
    configure_storage(env)
