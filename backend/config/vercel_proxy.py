"""Translate Vercel's edge headers to the existing private-proxy contract.

Vercel overwrites X-Forwarded-For to prevent IP spoofing. This adapter must
only run inside a Vercel Function, never in the standalone Gunicorn service.
https://vercel.com/docs/headers/request-headers#x-forwarded-for
"""

import os
from ipaddress import ip_address


class VercelProxy:
    def __init__(self, application):
        if os.environ.get("VERCEL") != "1":
            raise RuntimeError("The Vercel entrypoint requires the Vercel runtime")
        self.application = application

    def __call__(self, environ, start_response):
        try:
            client_ip = str(ip_address(environ.get("HTTP_X_FORWARDED_FOR", "")))
        except ValueError:
            return self.invalid_request(start_response)
        protocol = environ.get("HTTP_X_FORWARDED_PROTO", "")
        if protocol not in {"http", "https"}:
            return self.invalid_request(start_response)

        # Ignore the caller-supplied private-proxy headers. Only the address
        # supplied by Vercel's edge becomes the normalized application client.
        for header in (
            "HTTP_X_FORWARDED_FOR",
            "HTTP_X_REAL_IP",
            "HTTP_FORWARDED",
            "HTTP_X_FORWARDED_HOST",
        ):
            environ.pop(header, None)
        environ["REMOTE_ADDR"] = "127.0.0.1"
        environ["HTTP_X_VERIFIED_CLIENT_IP"] = client_ip
        environ["HTTP_X_FORWARDED_PROTO"] = protocol
        return self.application(environ, start_response)

    @staticmethod
    def invalid_request(start_response):
        body = b'{"code":"invalid_proxy","message":"Invalid edge request","errors":{}}'
        start_response(
            "400 Bad Request",
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
        )
        return [body]
