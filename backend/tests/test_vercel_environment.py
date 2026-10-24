import pytest

from config.vercel_environment import configure_storage


def test_tigris_integration_uses_private_storage_settings():
    env = {
        "TIGRIS_STORAGE_BUCKET": "private-test-bucket",
        "TIGRIS_STORAGE_ACCESS_KEY_ID": "synthetic-key",
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY": "synthetic-secret",
    }
    configure_storage(env)
    assert env["S3_BUCKET"] == "private-test-bucket"
    assert env["S3_ACCESS_KEY"] == "synthetic-key"
    assert env["S3_SECRET_KEY"] == "synthetic-secret"
    assert env["S3_ENDPOINT_URL"] == "https://t3.storage.dev"
    assert env["S3_REGION"] == "auto"


def test_explicit_s3_configuration_remains_authoritative():
    env = {
        "TIGRIS_STORAGE_BUCKET": "integration-bucket",
        "S3_BUCKET": "explicit-bucket",
        "S3_ACCESS_KEY": "explicit-key",
        "S3_SECRET_KEY": "explicit-secret",
        "S3_ENDPOINT_URL": "https://storage.example.test",
        "S3_REGION": "explicit-region",
    }
    original = env.copy()
    configure_storage(env)
    assert env == original


def test_incomplete_tigris_integration_fails_without_disclosing_values():
    env = {"TIGRIS_STORAGE_BUCKET": "sensitive-bucket-name"}
    with pytest.raises(RuntimeError) as error:
        configure_storage(env)
    assert "sensitive" not in str(error.value)
    assert "TIGRIS_STORAGE_ACCESS_KEY_ID" in str(error.value)


def test_unrelated_environment_is_unchanged():
    env = {"DATABASE_URL": "synthetic"}
    configure_storage(env)
    assert env == {"DATABASE_URL": "synthetic"}
