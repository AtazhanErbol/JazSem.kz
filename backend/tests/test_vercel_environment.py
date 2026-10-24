import pytest

from config.vercel_environment import configure_preview, configure_storage


def test_preview_uses_its_stable_branch_alias_for_login_and_activation():
    env = {
        "VERCEL_ENV": "preview",
        "VERCEL_BRANCH_URL": "jazsem-git-topic-team.vercel.app",
        "DJANGO_ALLOWED_HOSTS": "jazsem.vercel.app",
        "FRONTEND_URL": "https://stale.vercel.app",
        "CSRF_TRUSTED_ORIGINS": "https://stale.vercel.app",
    }
    configure_preview(env)
    assert env["FRONTEND_URL"] == "https://jazsem-git-topic-team.vercel.app"
    assert env["CSRF_TRUSTED_ORIGINS"] == env["FRONTEND_URL"]
    assert env["DJANGO_ALLOWED_HOSTS"] == "jazsem.vercel.app,jazsem-git-topic-team.vercel.app"
    original = env.copy()
    configure_preview(env)
    assert env == original


@pytest.mark.parametrize("host", ["", "*.vercel.app", "evil.test", "x.vercel.app/path"])
def test_invalid_preview_identity_fails_closed(host):
    with pytest.raises(RuntimeError, match="Invalid Vercel preview branch identity"):
        configure_preview({"VERCEL_ENV": "preview", "VERCEL_BRANCH_URL": host})


def test_production_retains_explicit_domain_configuration():
    env = {
        "VERCEL_ENV": "production",
        "VERCEL_BRANCH_URL": "preview.vercel.app",
        "FRONTEND_URL": "https://jazsem.vercel.app",
        "CSRF_TRUSTED_ORIGINS": "https://jazsem.vercel.app",
        "DJANGO_ALLOWED_HOSTS": "jazsem.vercel.app",
    }
    original = env.copy()
    configure_preview(env)
    assert env == original


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
