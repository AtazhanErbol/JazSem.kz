import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import JsonResponse
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
        },
        status=403,
    )


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.messages)
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "code": "conflict",
                "message": translate("Операция конфликтует с существующими данными."),
                "errors": {},
            },
            status=409,
        )
    response = drf_handler(exc, context)
    if response is None:
        logging.getLogger(__name__).error(
            "Unhandled API error: %s",
            type(exc).__name__,
            extra={"request_id": getattr(context.get("request"), "request_id", "")},
        )
        return Response(
            {
                "code": "server_error",
                "message": translate("Ошибка сервера. Повторите позже."),
                "errors": {},
            },
            status=500,
        )
    data = response.data
    response.data = {
        "code": getattr(exc, "default_code", "invalid"),
        "message": str(data.get("detail", "Проверьте введённые данные."))
        if isinstance(data, dict)
        else "Проверьте введённые данные.",
        "errors": data,
    }
    response.data = translate(response.data)
    return response
