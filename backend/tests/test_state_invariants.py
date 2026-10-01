import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.audit.models import AuditLog
from apps.courses.services import duplicate


def test_preflight_accepts_existing_learning_history(world):
    output = io.StringIO()
    call_command("release_preflight", stdout=output)
    assert '"enrollment.owner": 0' in output.getvalue()


@pytest.mark.django_db(transaction=True)
def test_preflight_empty_database_fails_with_schema_metadata_not_sql_exception():
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([(app, None) for app in {node[0] for node in targets}])
        output = io.StringIO()
        with pytest.raises(CommandError, match="Preflight requires"):
            call_command("release_preflight", legacy=True, stdout=output)
        report = json.loads(output.getvalue())
        assert report["missing_schema"] and report["deferred"] == []
    finally:
        MigrationExecutor(connection).migrate(targets)


def test_preflight_reports_conflict_counts_without_repair(world):
    from apps.accounts.models import User

    User.objects.filter(pk=world["student"].pk).update(owner_teacher=None)
    output = io.StringIO()
    with pytest.raises(CommandError):
        call_command("release_preflight", stdout=output)
    assert json.loads(output.getvalue())["enrollment.owner"] == 1
    world["student"].refresh_from_db()
    assert world["student"].owner_teacher_id is None


@pytest.mark.django_db(transaction=True)
def test_preflight_runs_on_legacy_schema_and_requires_full_check_after_additive_migrations():
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(
            [("accounts", "0002_alter_user_managers"), ("notifications", "0001_initial")]
        )
        output = io.StringIO()
        call_command("release_preflight", legacy=True, stdout=output)
        assert set(json.loads(output.getvalue())["deferred"]) == {
            "accounts.User.owner_teacher",
            "notifications.MailOutbox.status",
        }
        with pytest.raises(CommandError):
            call_command("release_preflight", stdout=io.StringIO())
        MigrationExecutor(connection).migrate(targets)
        output = io.StringIO()
        call_command("release_preflight", stdout=output)
        assert json.loads(output.getvalue())["deferred"] == []
    finally:
        MigrationExecutor(connection).migrate(targets)


@pytest.mark.parametrize("name", ["course", "version", "enrollment"])
def test_unknown_states_are_rejected_without_losing_history(world, name):
    obj = world[name]
    previous = obj.status
    with pytest.raises(IntegrityError), transaction.atomic():
        type(obj).objects.filter(pk=obj.pk).update(status="TYPO")
    obj.refresh_from_db()
    assert obj.status == previous


def test_content_audit_excludes_document_text_and_secrets(world, client_for):
    version = duplicate(world["version"], world["teacher"])
    topic = version.weeks.first().topics.first()
    response = client_for(world["teacher"]).patch(
        f"/api/v1/topics/{topic.pk}/", {"title": "Updated", "content": "PRIVATE DOCUMENT BODY"}
    )
    assert response.status_code == 200
    entry = AuditLog.objects.filter(entity_id=str(topic.pk), action="content.updated").get()
    assert entry.new_data["title"] == "Updated"
    assert "content" not in entry.new_data
    assert "PRIVATE" not in str(entry.old_data) + str(entry.new_data)


def test_course_and_material_overrides_preserve_content_audit(world, client_for):
    client = client_for(world["teacher"])
    response = client.post(
        "/api/v1/courses/",
        {
            "title": "Audit course",
            "discipline": str(world["discipline"].pk),
            "teacher": str(world["teacher"].pk),
            "description": "PRIVATE DESCRIPTION",
        },
        format="json",
    )
    assert response.status_code == 201
    entry = AuditLog.objects.get(entity_id=response.data["id"], action="content.created")
    assert entry.new_data["title"] == "Audit course" and "description" not in entry.new_data
    copied = duplicate(world["version"], world["teacher"])
    topic = copied.weeks.first().topics.first()
    response = client.post(
        "/api/v1/materials/",
        {
            "topic": str(topic.pk),
            "title": "Audit material",
            "content": "PRIVATE BODY",
            "type": "TEXT",
        },
        format="json",
    )
    assert response.status_code == 201
    material = response.data["id"]
    assert AuditLog.objects.filter(entity_id=material, action="content.created").count() == 1
    response = client.patch(
        f"/api/v1/materials/{material}/",
        {"title": "Revised", "content": "PRIVATE NEW BODY"},
        format="json",
    )
    assert response.status_code == 200
    entry = AuditLog.objects.get(entity_id=material, action="content.updated")
    assert entry.old_data["title"] == "Audit material" and entry.new_data["title"] == "Revised"
    assert "PRIVATE" not in str(entry.old_data) + str(entry.new_data)
