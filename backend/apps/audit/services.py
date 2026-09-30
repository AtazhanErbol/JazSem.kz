from apps.common.request_context import request_context

from .models import AuditLog


def selected_fields(obj):
    """Intentionally omit bodies, files, credentials and student answers."""
    allowed = {
        "academics.discipline": ["name", "code", "status"],
        "academics.studygroup": ["name", "teacher_id", "status"],
        "courses.course": ["title", "teacher_id", "discipline_id", "status"],
        "courses.week": ["title", "number", "order"],
        "courses.topic": ["title", "order", "is_required"],
        "materials.material": ["title", "type", "size", "is_required"],
        "assignments.assignment": ["title", "deadline", "max_score", "is_required"],
        "testing.test": [
            "title",
            "max_attempts",
            "time_limit_minutes",
            "passing_score",
            "available_from",
            "available_until",
        ],
        "testing.question": ["type", "score", "order"],
        "testing.answeroption": ["order"],
        "grading.gradingcomponent": ["kind", "weight"],
        "cms.contentblock": ["key", "language", "is_published"],
    }
    return {key: str(getattr(obj, key)) for key in allowed.get(obj._meta.label_lower, [])}


def record(user, action, obj, old=None, new=None):
    # Only explicitly selected business fields are accepted at call sites.
    AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=obj._meta.label,
        entity_id=str(obj.pk),
        old_data=old or {},
        ip=request_context.get().get("ip"),
        new_data=new or {},
    )
