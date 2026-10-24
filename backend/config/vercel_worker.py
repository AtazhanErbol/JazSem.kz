"""Private, queue-triggered Celery subscriber, with the production configuration."""

import os

import django

from config.vercel_environment import configure_runtime

configure_runtime(os.environ)

# tesserocr's cysignals dependency installs signal handlers on first import.
# Load it on the entrypoint's main thread before the sync Celery task thread
# can initialize OCR; importing it for the first time there raises ValueError.
import tesserocr  # noqa: E402,F401

django.setup()

from config.celery import app  # noqa: E402

app.autodiscover_tasks(force=True)
__all__ = ("app",)
