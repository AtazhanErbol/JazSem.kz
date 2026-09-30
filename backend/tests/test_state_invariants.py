import io

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.audit.models import AuditLog
from apps.courses.services import duplicate


def test_preflight_accepts_existing_learning_history(world):
    output = io.StringIO()
    call_command("release_preflight", stdout=output)
    assert '"enrollment.owner": 0' in output.getvalue()


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
