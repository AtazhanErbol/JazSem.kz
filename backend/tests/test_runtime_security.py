import json
import smtplib
import ssl
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.common.telemetry import scrub_event
from config.redis_tls import redis_tls_options


def test_throttle_dependency_outage_is_structured_and_fails_closed():
    from redis.exceptions import ConnectionError
    from rest_framework.test import APIClient

    with patch(
        "rest_framework.throttling.SimpleRateThrottle.cache.get",
        side_effect=ConnectionError("private-url"),
    ):
        response = APIClient().get("/api/v1/auth/login/", HTTP_ACCEPT_LANGUAGE="kk")
    assert response.status_code == 503
    assert response.data["code"] == "service_unavailable"
    assert response["Retry-After"] == "30"
    assert "private-url" not in str(response.data)
    assert "уақытша" in response.data["message"]


@pytest.mark.parametrize(
    "error,code",
    [
        (smtplib.SMTPDataError(451, b"temporary"), "SMTP_UNAVAILABLE"),
        (smtplib.SMTPDataError(550, b"permanent"), "SMTP_PERMANENT_FAILURE"),
        (smtplib.SMTPRecipientsRefused({"a@example.test": (451, b"busy")}), "SMTP_UNAVAILABLE"),
        (smtplib.SMTPRecipientsRefused({"a@example.test": (550, b"gone")}), "RECIPIENT_REJECTED"),
    ],
)
def test_smtp_response_classification(error, code):
    from apps.notifications.tasks import delivery_error

    assert delivery_error(error) == code


def test_redis_tls_is_verified_and_url_cannot_override_policy():
    assert redis_tls_options("redis://localhost/0") is None
    options = redis_tls_options("rediss://:synthetic@localhost/0", "/ca.pem")
    assert options == {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_check_hostname": True,
        "ssl_ca_certs": "/ca.pem",
    }
    for parameter in ("ssl_cert_reqs=none", "ssl_check_hostname=false", "ssl_ca_certs=evil"):
        with pytest.raises(ImproperlyConfigured):
            redis_tls_options("rediss://localhost/0?" + parameter)


def test_error_telemetry_drops_request_secrets_and_student_content():
    secret = "PRIVATE-SYNTHETIC-TOKEN"
    event = {
        "request": {
            "url": f"https://user:{secret}@site/reset?token={secret}#secret",
            "data": secret,
            "headers": {"Cookie": secret},
            "method": "POST",
        },
        "message": secret,
        "logentry": {"message": secret},
        "extra": {"x": secret},
        "user": {"email": secret},
        "breadcrumbs": [{"message": secret}],
        "contexts": {"trace": {"data": secret}},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": secret,
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "app.py",
                                "lineno": 7,
                                "vars": {"answer": secret},
                                "context_line": secret,
                                "pre_context": [secret],
                                "post_context": [secret],
                            }
                        ]
                    },
                }
            ]
        },
    }
    cleaned = scrub_event(event, {})
    assert secret not in json.dumps(cleaned)
    assert cleaned["request"] == {"method": "POST", "url": "https://site/reset"}
    assert cleaned["exception"]["values"][0]["stacktrace"]["frames"] == [
        {"filename": "app.py", "lineno": 7}
    ]
