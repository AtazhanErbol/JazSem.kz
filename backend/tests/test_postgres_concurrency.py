from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from rest_framework.test import APIClient

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="Requires real PostgreSQL row locks; CI provides PostgreSQL",
    ),
]


def race(*operations):
    barrier = Barrier(len(operations))

    def run(operation):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return operation()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        futures = [pool.submit(run, op) for op in operations]
        return [future.result(timeout=20) for future in futures]


def client(user):
    result = APIClient()
    result.force_authenticate(user)
    return result


def test_concurrent_admin_deactivation_leaves_active_administrator(world):
    from apps.accounts.models import User

    other = User.objects.create_user(
        username="second-admin",
        email="second-admin@example.test",
        role="ADMIN",
        must_change_password=False,
    )
    first = world["admin"]
    responses = race(
        lambda: (
            client(first)
            .patch(f"/api/v1/users/{other.pk}/", {"is_active": False}, format="json")
            .status_code
        ),
        lambda: client(other).post(f"/api/v1/users/{first.pk}/deactivate/").status_code,
    )
    assert sorted(responses) in [[200, 403], [204, 403]]
    assert User.objects.filter(role="ADMIN", is_active=True).count() == 1


def test_concurrent_enrollment_is_idempotent(world):
    from apps.enrollments.models import Enrollment

    responses = race(
        *[
            lambda: (
                client(world["teacher"])
                .post(
                    f"/api/v1/courses/{world['course'].pk}/assign/",
                    {"student": str(world["student"].pk)},
                )
                .status_code
            )
            for _ in range(2)
        ]
    )
    assert responses == [200, 200]
    assert Enrollment.objects.filter(student=world["student"], course=world["course"]).count() == 1
