import logging
import uuid

from .request_context import request_context


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        token = request_context.set(
            {"request_id": request.request_id, "ip": request.META.get("REMOTE_ADDR")}
        )
        try:
            response = self.get_response(request)
        finally:
            request_context.reset(token)
        response["X-Request-ID"] = request.request_id
        logging.getLogger("http").info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
            extra={"request_id": request.request_id},
        )
        return response
