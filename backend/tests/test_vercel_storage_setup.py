import urllib.error
from unittest.mock import Mock

import pytest

from config.vercel_storage_setup import verify_direct_upload


def test_real_transport_probe_checks_cors_size_signed_download_and_privacy(monkeypatch):
    client = Mock()
    client.generate_presigned_post.return_value = {
        "url": "https://storage.example.test/",
        "fields": {"policy": "synthetic"},
    }
    client.generate_presigned_url.return_value = (
        "https://storage.example.test/private/object?signature=synthetic"
    )
    client.head_object.return_value = {"ContentLength": 25 * 1024 * 1024}
    methods = []

    def open_url(request, **kwargs):
        if isinstance(request, str):
            assert "?" not in request
            methods.append("anonymous")
            raise urllib.error.HTTPError(request, 403, "Forbidden", {}, None)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        if request.get_method() == "POST":
            assert request.data.count(b"a" * 1024) >= 25 * 1024
            assert request.data.rfind(b'name="file"') > request.data.find(b'name="policy"')
            response.headers = {"Access-Control-Allow-Origin": "https://app.example.test"}
            methods.append("post")
        else:
            assert request.headers["Range"] == "bytes=0-15"
            response.read.return_value = b"a" * 16
            response.headers = {"Content-Disposition": 'attachment; filename="check.txt"'}
            methods.append("signed")
        return response

    monkeypatch.setattr("config.vercel_storage_setup.urllib.request.urlopen", open_url)
    verify_direct_upload(client, "private-test", "https://app.example.test")
    assert methods == ["post", "signed", "anonymous"]
    client.delete_object.assert_called_once()


def test_probe_cleanup_runs_when_storage_upload_fails(monkeypatch):
    client = Mock()
    client.generate_presigned_post.return_value = {
        "url": "https://storage.example.test/",
        "fields": {},
    }
    monkeypatch.setattr(
        "config.vercel_storage_setup.urllib.request.urlopen", Mock(side_effect=OSError("synthetic"))
    )
    with pytest.raises(OSError):
        verify_direct_upload(client, "private-test", "https://app.example.test")
    client.delete_object.assert_called_once()
