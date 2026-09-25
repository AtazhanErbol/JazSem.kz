from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers


def annotate_actions():
    from apps.academics.views import GroupViewSet
    from apps.ai.views import DraftViewSet, GenerationSerializer, JobViewSet, SourceViewSet
    from apps.assignments.models import Submission
    from apps.assignments.views import AssignmentViewSet, SubmissionViewSet
    from apps.common.serializers import serializer_for
    from apps.courses.models import CourseVersion
    from apps.courses.views import CourseViewSet
    from apps.testing.models import TestAttempt
    from apps.testing.views import AttemptViewSet, TestViewSet

    def mark(view, method, name, fields, response=None):
        kwargs = {"request": inline_serializer(name=name, fields=fields)}
        if response is not None:
            kwargs["responses"] = response
        setattr(view, method, extend_schema(**kwargs)(getattr(view, method)))

    for method in ["publish", "duplicate"]:
        mark(
            CourseViewSet,
            method,
            "Course" + method.title(),
            {"version": serializers.UUIDField()},
            serializer_for(CourseVersion),
        )
    mark(CourseViewSet, "assign", "IndividualAssignment", {"student": serializers.UUIDField()})
    mark(GroupViewSet, "assign", "GroupAssignment", {"course": serializers.UUIDField()})
    mark(GroupViewSet, "members", "GroupMember", {"student": serializers.UUIDField()})
    mark(GroupViewSet, "remove_member", "RemoveMember", {"student": serializers.UUIDField()})
    mark(
        AssignmentViewSet,
        "submit",
        "SubmitWork",
        {
            "text_answer": serializers.CharField(required=False),
            "files": serializers.ListField(child=serializers.FileField(), required=False),
        },
        serializer_for(Submission),
    )
    mark(
        SubmissionViewSet,
        "grade",
        "GradeWork",
        {
            "score": serializers.DecimalField(max_digits=10, decimal_places=2),
            "comment": serializers.CharField(required=False),
        },
        serializer_for(Submission),
    )
    mark(
        SubmissionViewSet,
        "revision",
        "ReviseWork",
        {"comment": serializers.CharField()},
        serializer_for(Submission),
    )
    mark(
        AttemptViewSet,
        "answer",
        "SaveAnswer",
        {
            "question": serializers.UUIDField(),
            "selected_options": serializers.ListField(child=serializers.UUIDField()),
        },
    )
    mark(AttemptViewSet, "finish", "FinishAttempt", {}, serializer_for(TestAttempt))
    mark(TestViewSet, "start", "StartAttempt", {}, serializer_for(TestAttempt))
    JobViewSet.create = extend_schema(request=GenerationSerializer)(JobViewSet.create)
    mark(
        SourceViewSet,
        "create",
        "UploadSource",
        {"course": serializers.UUIDField(), "file": serializers.FileField()},
    )
    mark(DraftViewSet, "partial_update", "EditAIDraft", {"data": serializers.JSONField()})
    mark(
        DraftViewSet,
        "regenerate",
        "RegenerateTopic",
        {
            "week_index": serializers.IntegerField(min_value=0),
            "topic_index": serializers.IntegerField(min_value=0),
            "instruction": serializers.CharField(),
        },
    )
    mark(DraftViewSet, "confirm", "ImportDraft", {}, serializer_for(CourseVersion))
