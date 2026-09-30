from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


def test_admin_created_student_can_join_owner_group_and_course(world, client_for):
    admin = client_for(world["admin"])
    created = admin.post(
        "/api/v1/users/",
        {
            "email": "new-student@example.test",
            "first_name": "New",
            "last_name": "Student",
            "role": "STUDENT",
            "owner_teacher": str(world["teacher"].pk),
        },
        format="json",
    )
    assert created.status_code == 201
    student_id = created.data["id"]
    member = admin.post(f"/api/v1/groups/{world['group'].pk}/members/", {"student": student_id})
    assert member.status_code == 201
    assigned = admin.post(f"/api/v1/courses/{world['course'].pk}/assign/", {"student": student_id})
    assert assigned.status_code == 200
    assert created.data["created_by"] == world["admin"].pk
    assert client_for(world["teacher"]).get(f"/api/v1/users/{student_id}/").status_code == 200
    assert client_for(world["other"]).get(f"/api/v1/users/{student_id}/").status_code == 404


@pytest.mark.parametrize("resource,item", [("questions", "question"), ("options", "correct")])
def test_student_cannot_read_authoring_questions_before_start(world, client_for, resource, item):
    test = world["test"]
    test.available_from = timezone.now() + timedelta(days=1)
    test.save()
    student = client_for(world["student"])
    assert student.post(f"/api/v1/tests/{test.pk}/start/").status_code == 400
    assert student.get(f"/api/v1/{resource}/?test={test.pk}").status_code == 403
    assert student.get(f"/api/v1/{resource}/{world[item].pk}/").status_code == 403
    assert (
        client_for(world["teacher"]).get(f"/api/v1/{resource}/{world[item].pk}/").status_code == 200
    )


def test_patch_cannot_bypass_self_deactivation_policy(world, client_for):
    response = client_for(world["admin"]).patch(
        f"/api/v1/users/{world['admin'].pk}/", {"is_active": False}, format="json"
    )
    assert response.status_code == 403
    world["admin"].refresh_from_db()
    assert world["admin"].is_active


@pytest.mark.parametrize("answer", [None, {}, [], 7, True])
def test_malformed_submission_is_a_field_error_not_server_error(world, client_for, answer):
    response = client_for(world["student"]).post(
        f"/api/v1/assignments/{world['assignment'].pk}/submit/",
        {"text_answer": answer},
        format="json",
    )
    assert response.status_code == 400
    assert "text_answer" in response.data["errors"]


def test_owner_cannot_be_injected_or_changed_after_learning_started(world, client_for):
    teacher = client_for(world["teacher"])
    response = teacher.post(
        "/api/v1/users/",
        {
            "email": "injected@example.test",
            "role": "STUDENT",
            "owner_teacher": str(world["other"].pk),
        },
        format="json",
    )
    assert response.status_code == 403
    admin = client_for(world["admin"])
    url = f"/api/v1/users/{world['student'].pk}/"
    assert (
        admin.patch(url, {"owner_teacher": str(world["other"].pk)}, format="json").status_code
        == 400
    )
    assert admin.patch(url, {"owner_teacher": None}, format="json").status_code == 400
    world["student"].refresh_from_db()
    assert world["student"].owner_teacher_id == world["teacher"].pk
    assert world["enrollment"].course_version_id == world["version"].pk


def test_unassigned_student_is_explicit_and_can_be_assigned_without_history(world, client_for):
    admin = client_for(world["admin"])
    created = admin.post(
        "/api/v1/users/",
        {"email": "unassigned@example.test", "role": "STUDENT", "owner_teacher": None},
        format="json",
    )
    assert created.status_code == 201
    url = f"/api/v1/users/{created.data['id']}/"
    assert client_for(world["teacher"]).get(url).status_code == 404
    assert (
        admin.patch(url, {"owner_teacher": str(world["teacher"].pk)}, format="json").status_code
        == 200
    )
    assert client_for(world["teacher"]).get(url).status_code == 200
    assert (
        admin.post(
            "/api/v1/users/", {"email": "implicit@example.test", "role": "STUDENT"}, format="json"
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "resource,action,key",
    [
        ("courses", "publish", "version"),
        ("courses", "assign", "student"),
        ("groups", "members", "student"),
        ("groups", "remove-member", "student"),
        ("groups", "assign", "course"),
    ],
)
def test_invalid_action_uuid_is_field_error(world, client_for, resource, action, key):
    item = world["course" if resource == "courses" else "group"]
    response = client_for(world["admin"]).post(
        f"/api/v1/{resource}/{item.pk}/{action}/", {key: "not-a-uuid"}
    )
    assert response.status_code == 400
    assert key in response.data["errors"]


@pytest.mark.django_db(transaction=True)
def test_ownership_data_migration_preserves_creator_and_unassigned_records():
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([("accounts", "0002_alter_user_managers")])
        old_user = executor.loader.project_state(
            [("accounts", "0002_alter_user_managers")]
        ).apps.get_model("accounts", "User")
        teacher = old_user.objects.create(
            username="m-teacher", email="m-teacher@example.test", role="TEACHER"
        )
        admin = old_user.objects.create(
            username="m-admin", email="m-admin@example.test", role="ADMIN"
        )
        owned = old_user.objects.create(
            username="m-owned", email="m-owned@example.test", role="STUDENT", created_by=teacher
        )
        unassigned = old_user.objects.create(
            username="m-unassigned",
            email="m-unassigned@example.test",
            role="STUDENT",
            created_by=admin,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        from apps.accounts.models import User

        assert User.objects.get(pk=owned.pk).owner_teacher_id == teacher.pk
        assert User.objects.get(pk=owned.pk).created_by_id == teacher.pk
        assert User.objects.get(pk=unassigned.pk).owner_teacher_id is None
        assert User.objects.get(pk=unassigned.pk).created_by_id == admin.pk
    finally:
        MigrationExecutor(connection).migrate(targets)
