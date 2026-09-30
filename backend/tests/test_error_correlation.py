import logging
from types import SimpleNamespace

from apps.common.errors import exception_handler


def test_unexpected_error_has_correlation_and_safe_stack_without_payload(caplog):
    request = SimpleNamespace(request_id="synthetic-request-id")
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("SECRET password and document text")
        except RuntimeError as error:
            response = exception_handler(error, {"request": request})
    assert response.status_code == 500 and response.data["request_id"] == request.request_id
    assert "SECRET" not in str(response.data) + caplog.text
    record = next(item for item in caplog.records if item.name == "apps.common.errors")
    assert record.request_id == request.request_id
    assert record.traceback_frames and record.error_type == "RuntimeError"
