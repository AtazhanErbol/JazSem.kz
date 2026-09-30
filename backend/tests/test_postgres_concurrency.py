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


def test_concurrent_admin_teacher_generation_has_one_winner(world, settings):
    from unittest.mock import patch

    from apps.ai.models import AIJob
    from tests.test_ai_recovery import configured, source

    configured(settings)
    document = source(world)
    data = {
        "course": str(world["course"].pk),
        "weeks": 1,
        "language": "ru",
        "sources": [str(document.pk)],
    }
    with patch("apps.ai.views.require_worker"):
        responses = race(
            *[
                lambda actor=world[role]: (
                    client(actor).post("/api/v1/ai-jobs/", data, format="json").status_code
                )
                for role in ["admin", "teacher"]
            ]
        )
    assert sorted(responses) == [202, 409]
    assert AIJob.objects.filter(course=world["course"], status="QUEUED").count() == 1


def test_concurrent_mail_claim_has_one_owner(world):
    from apps.notifications.models import MailOutbox
    from apps.notifications.services import queue_mail
    from apps.notifications.tasks import claim_mail

    MailOutbox.objects.all().delete()
    queue_mail(world["student"], "Synthetic", "Synthetic")
    queued = MailOutbox.objects.get()
    responses = race(*[lambda: claim_mail(queued.pk) is not None for _ in range(2)])
    assert sorted(responses) == [False, True]
    queued.refresh_from_db()
    assert queued.attempts == 1


def test_concurrent_budget_reservation_never_exceeds_cap(world, settings):
    from decimal import Decimal

    from apps.ai.budget import reserve_budget
    from apps.ai.models import AIBudgetDay
    from tests.test_ai_recovery import configured

    configured(settings)
    settings.AI_DAILY_BUDGET_USD = "0.012"

    def reserve():
        try:
            reserve_budget({}, {}, 100)
            return True
        except ValueError:
            return False

    assert sorted(race(reserve, reserve)) == [False, True]
    assert Decimal("0") < AIBudgetDay.objects.get().reserved_usd <= Decimal("0.012")


def test_start_and_expire_follow_one_lock_order(world):
    """Force the former Enrollment->Attempt / Attempt->Enrollment deadlock."""
    from datetime import timedelta
    from threading import Event

    from django.db import transaction
    from django.utils import timezone

    from apps.enrollments.models import Enrollment
    from apps.testing.models import TestAttempt
    from apps.testing.services import finalize, start

    attempt = start(world["test"], world["student"])
    TestAttempt.objects.filter(pk=attempt.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    enrollment_locked, finish_lock_started = Event(), Event()

    def starting():
        with transaction.atomic():
            Enrollment.objects.select_for_update().get(pk=world["enrollment"].pk)
            enrollment_locked.set()
            assert finish_lock_started.wait(10)
            return start(world["test"], world["student"]).attempt_number

    def finishing():
        assert enrollment_locked.wait(10)

        def observe(execute, sql, params, many, context):
            locking = "FOR UPDATE" in sql.upper()
            if locking and "enrollments_enrollment" in sql:
                finish_lock_started.set()
            result = execute(sql, params, many, context)
            if locking and "testing_testattempt" in sql:
                finish_lock_started.set()
            return result

        with connection.execute_wrapper(observe):
            return finalize(attempt, world["student"]).status

    assert race(starting, finishing) == [2, "EXPIRED"]
    assert TestAttempt.objects.filter(test=world["test"], status="IN_PROGRESS").count() == 1
