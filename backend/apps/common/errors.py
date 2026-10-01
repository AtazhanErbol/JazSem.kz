import logging
import traceback

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler

from .translations import translate


def csrf_failure(request, reason=""):
    return JsonResponse(
        {
            "code": "csrf_failed",
            "message": translate("Проверка безопасности не пройдена. Обновите страницу."),
            "errors": {},
            "request_id": getattr(request, "request_id", ""),
        },
        status=403,
    )


def exception_handler(exc, context):
    request_id = getattr(context.get("request"), "request_id", "")
    if isinstance(exc, (RedisConnectionError, RedisTimeoutError)):
        # A failed throttle/cache dependency must fail closed, without exposing
        # connection URLs or turning a temporary outage into an opaque 500.
        return Response(
            {
                "code": "service_unavailable",
                "message": translate("Сервис временно недоступен. Повторите позже."),
                "errors": {},
                "request_id": request_id,
            },
            status=503,
            headers={"Retry-After": "30"},
        )
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.messages)
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "code": "conflict",
                "message": translate("Операция конфликтует с существующими данными."),
                "errors": {},
                "request_id": request_id,
            },
            status=409,
        )
    response = drf_handler(exc, context)
    if response is None:
        logging.getLogger(__name__).error(
            "Unhandled API error: %s",
            type(exc).__name__,
            extra={
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "traceback_frames": [
                    {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                    for frame in traceback.extract_tb(exc.__traceback__)
                ],
            },
        )
        return Response(
            {
                "code": "server_error",
                "message": translate("Ошибка сервера. Повторите позже."),
                "errors": {},
                "request_id": request_id,
            },
            status=500,
        )
    data = response.data
    response.data = {
        "request_id": request_id,
        "code": getattr(exc, "default_code", "invalid"),
        "message": str(data.get("detail", "Проверьте введённые данные."))
        if isinstance(data, dict)
        else "Проверьте введённые данные.",
        "errors": data,
    }
    response.data = translate(response.data)
    return response
