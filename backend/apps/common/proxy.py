from ipaddress import ip_address, ip_network

from django.conf import settings
from django.http import JsonResponse

from .request_context import request_context


class TrustedProxyMiddleware:
    """Only the configured private peer may supply the normalized client IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        peer = request.META.get("REMOTE_ADDR", "")
        verified = request.META.pop("HTTP_X_VERIFIED_CLIENT_IP", "")
        request.META.pop("HTTP_X_FORWARDED_FOR", None)
        request.META.pop("HTTP_X_REAL_IP", None)
        try:
            trusted = any(
                ip_address(peer) in ip_network(cidr) for cidr in settings.TRUSTED_PROXY_CIDRS
            )
        except ValueError:
            trusted = False
        if trusted:
            try:
                request.META["REMOTE_ADDR"] = str(ip_address(verified))
            except ValueError:
                return JsonResponse(
                    {
                        "code": "invalid_proxy",
                        "message": "Invalid proxy client address",
                        "errors": {},
                        "request_id": getattr(request, "request_id", ""),
                    },
                    status=400,
                )
        else:
            request.META.pop("HTTP_X_FORWARDED_PROTO", None)
        # Validate Host even on liveness and static API views.
        request.get_host()
        request_context.set({**request_context.get(), "ip": request.META.get("REMOTE_ADDR")})
        return self.get_response(request)
