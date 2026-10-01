"""Explicit test-only overlay, mounted outside the production image."""

import os

from config.settings.production import *
from django.core.exceptions import ImproperlyConfigured

if (
    os.environ.get("E2E_FAKE_PROVIDER") != "1"
    or DATABASES["default"]["NAME"] != "jazsem_rc_runtime"
    or os.environ.get("S3_BUCKET") != "jazsem-acceptance-private"
    or os.environ.get("DJANGO_ALLOWED_HOSTS") != "rc.example.test"
):
    raise ImproperlyConfigured(
        "Fake-provider overlay requires the disposable acceptance project"
    )
ACCEPTANCE_SYNTHETIC = True
ACCEPTANCE_CONTROL_DIR = "/control"
INSTALLED_APPS = [*INSTALLED_APPS, "tests.acceptance_provider.SyntheticProviderConfig"]
AI_ENABLED = True
OPENAI_API_KEY = "synthetic-acceptance-not-a-provider-key"
OPENAI_MODEL = "synthetic-no-network"
AI_INPUT_PRICE = "0.01"
AI_OUTPUT_PRICE = "0.02"
