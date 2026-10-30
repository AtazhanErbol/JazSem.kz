"""Forward-only release preparation against the attached deployment database."""

import os

import django

from config.vercel_environment import configure_runtime, require_preview_isolation
from config.vercel_storage_setup import main as initialize_storage
from config.vercel_storage_setup import safe_error


def main():
    require_preview_isolation(os.environ)
    # Storage preparation is independent of SMTP and can prove the upload path
    # before the strict production configuration validation stops an incomplete build.
    try:
        initialize_storage()
    except Exception as error:
        raise SystemExit(safe_error(error)) from None
    configure_runtime(os.environ)
    django.setup()
    from django.core.management import call_command

    call_command("migrate", interactive=False)
    call_command("release_preflight")
    call_command("check", deploy=True, fail_level="WARNING")
    call_command("collectstatic", interactive=False)
    call_command("storage_probe", initialize=True)
    if os.environ.get("INITIAL_ADMIN_EMAIL"):
        call_command("bootstrap_owner", email=os.environ["INITIAL_ADMIN_EMAIL"])


if __name__ == "__main__":
    main()
