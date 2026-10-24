"""Vercel-only WSGI entrypoint; standalone production keeps config.wsgi."""

import os

from config.vercel_environment import configure_runtime
from config.vercel_proxy import VercelProxy

configure_runtime(os.environ)

from config.wsgi import application as django_application  # noqa: E402

application = VercelProxy(django_application)
