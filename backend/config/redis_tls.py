"""One verified TLS policy for cache, Celery broker and result backend."""

import ssl
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import ImproperlyConfigured


def redis_tls_options(url, ca_file=""):
    parsed = urlsplit(url)
    # URL parameters override client keyword options in redis/kombu. Do not let
    # an accepted URL silently weaken verification or select another trust root.
    if any(key.startswith("ssl_") for key in parse_qs(parsed.query)):
        raise ImproperlyConfigured(
            "Configure Redis TLS with REDIS_SSL_CA_CERTS, not URL ssl_* parameters."
        )
    if parsed.scheme != "rediss":
        return None
    options = {"ssl_cert_reqs": ssl.CERT_REQUIRED, "ssl_check_hostname": True}
    if ca_file:
        options["ssl_ca_certs"] = ca_file
    return options
