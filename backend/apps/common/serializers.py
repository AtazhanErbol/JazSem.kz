from rest_framework import serializers

from apps.common.permissions import is_teacher

_serializers = {}

# Explicit public contracts: adding a model column must not expose it through API.
_contracts = {
    "assignments.submission": "assignment student attempt_number text_answer submitted_at status score teacher_comment graded_by graded_at",
    "assignments.submissionfile": "submission file original_filename mime_type size",
    "testing.testattempt": "test student attempt_number started_at expires_at submitted_at status score question_order option_order",
    "testing.question": "test text type score order explanation source_chunks",
    "testing.answeroption": "question text is_correct order",
    "testing.test": "topic title description max_score time_limit_minutes max_attempts shuffle_questions shuffle_answers available_from available_until passing_score status is_required is_final",
    "enrollments.enrollment": "student course course_version source_type assigned_group assigned_by assigned_at started_at completed_at status access_revoked",
    "enrollments.enrollmentsource": "enrollment source_key group_assignment assigned_by",
}
_read_only = {
    "assignments.submission",
    "assignments.submissionfile",
    "testing.testattempt",
    "enrollments.enrollment",
    "enrollments.enrollmentsource",
}


class ScopedSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("request").user if self.context.get("request") else None
        if user and not is_teacher(user):
            for key in ["is_correct", "explanation", "source_chunks"]:
                data.pop(key, None)
        if "file" in data:
            data["file"] = bool(instance.file)
        data.pop("extracted_text", None)
        return data


def serializer_for(model, readonly=()):
    key = (model, tuple(readonly))
    if key in _serializers:
        return _serializers[key]
    fields = (
        ["id", "created_at", "updated_at", *_contracts[model._meta.label_lower].split()]
        if model._meta.label_lower in _contracts
        else "__all__"
    )
    result = type(
        model.__name__ + ("Write" if readonly else "") + "Serializer",
        (ScopedSerializer,),
        {
            "Meta": type(
                "Meta",
                (),
                {
                    "model": model,
                    "fields": fields,
                    "read_only_fields": fields
                    if model._meta.label_lower in _read_only
                    else ["id", "created_at", "updated_at", *readonly],
                },
            )
        },
    )
    _serializers[key] = result
    return result
