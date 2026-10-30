import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.mark.django_db
def test_first_owner_has_no_default_password_and_uses_existing_reset_flow():
    call_command("bootstrap_owner", email="owner@example.test")
    user = User.objects.get(username="owner")
    assert user.role == "ADMIN" and user.is_superuser
    assert not user.has_usable_password()
    client = APIClient()
    response = client.post(
        "/api/v1/auth/reset-password/",
        {
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
            "password": "Synthetic-owner-pass-835!",
        },
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Synthetic-owner-pass-835!")


@pytest.mark.django_db
def test_redeploy_never_replaces_existing_owner_or_password():
    user = User.objects.create_superuser("existing", "existing@example.test", "Synthetic-test-835!")
    original = user.password
    call_command("bootstrap_owner", email="different@example.test")
    user.refresh_from_db()
    assert user.password == original and User.objects.count() == 1


@pytest.mark.django_db
def test_bootstrap_cannot_promote_a_user_in_nonempty_database():
    user = User.objects.create_user("existing", "existing@example.test", role="TEACHER")
    with pytest.raises(CommandError):
        call_command("bootstrap_owner", email="existing@example.test")
    user.refresh_from_db()
    assert not user.is_superuser and user.role == "TEACHER"
