"""Vercel-only WSGI entrypoint; standalone production keeps config.wsgi."""

import os

from config.vercel_proxy import VercelProxy

if os.environ.get("VERCEL") != "1":
    raise RuntimeError("The Vercel entrypoint requires the Vercel runtime")

# This peer represents the in-process adapter, not an Internet proxy range.
if os.environ.setdefault("TRUSTED_PROXY_CIDRS", "127.0.0.1/32") != "127.0.0.1/32":
    raise RuntimeError("Vercel requires the fixed in-process proxy peer")
if (
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
    != "config.settings.production"
):
    raise RuntimeError("The Vercel entrypoint requires production settings")

from config.wsgi import application as django_application  # noqa: E402

application = VercelProxy(django_application)
