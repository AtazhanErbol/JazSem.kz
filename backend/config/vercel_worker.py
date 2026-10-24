"""Private, queue-triggered Celery subscriber, with the production configuration."""

import os

import django

from config.vercel_environment import configure_runtime

configure_runtime(os.environ)
django.setup()

from config.celery import app  # noqa: E402

app.autodiscover_tasks(force=True)
__all__ = ("app",)
