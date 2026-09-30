from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.assignments.models import Assignment, Submission, SubmissionFile
from apps.assignments.services import review, submit
from apps.common.api import ReadOnlyScoped, ScopedViewSet, private_response, representation
from apps.common.inputs import GradeInput, ReviewInput, RevisionInput, SubmissionInput, validated
from apps.common.serializers import serializer_for


class AssignmentDisplaySerializer(serializer_for(Assignment)):
    course_id = serializers.UUIDField(source="topic.week.course_version.course_id", read_only=True)
    course_version_id = serializers.UUIDField(source="topic.week.course_version_id", read_only=True)


class AssignmentViewSet(ScopedViewSet):
    queryset = Assignment.objects.select_related("topic__week__course_version")
    serializer_class = AssignmentDisplaySerializer
    filterset_fields = ["status", "topic"]
    ordering_fields = ["created_at", "deadline", "title", "order"]

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        data = validated(request, SubmissionInput)
        obj = submit(
            self.get_object(),
            request.user,
            data["text_answer"],
            data.get("files", []),
        )
        return Response(representation(obj, request), status=201)


class SubmissionDisplaySerializer(serializer_for(Submission)):
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    max_score = serializers.IntegerField(source="assignment.max_score", read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta(serializer_for(Submission).Meta):
        fields = [
            *serializer_for(Submission).Meta.fields,
            "assignment_title",
            "max_score",
            "student_name",
        ]
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        return obj.student.get_full_name() or obj.student.email


class SubmissionViewSet(ReadOnlyScoped):
    queryset = Submission.objects.select_related("assignment", "student")
    serializer_class = SubmissionDisplaySerializer
    filterset_fields = ["status", "assignment", "student"]
    search_fields = ["student__email", "assignment__title"]

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        data = validated(request, GradeInput)
        return Response(
            representation(
                review(
                    self.get_object(),
                    request.user,
                    "grade",
                    data["score"],
                    data["comment"],
                ),
                request,
            )
        )

    @action(detail=True, methods=["post"], url_path="request-revision")
    def revision(self, request, pk=None):
        data = validated(request, RevisionInput)
        return Response(
            representation(
                review(
                    self.get_object(),
                    request.user,
                    "revision",
                    comment=data["comment"],
                ),
                request,
            )
        )

    @action(detail=True, methods=["post"], url_path="start-review")
    def review(self, request, pk=None):
        data = validated(request, ReviewInput)
        return Response(
            representation(
                review(self.get_object(), request.user, "review", comment=data["comment"]), request
            )
        )

    @action(detail=True, methods=["get"])
    def files(self, request, pk=None):
        return Response([representation(file, request) for file in self.get_object().files.all()])


class SubmissionFileViewSet(ReadOnlyScoped):
    queryset = SubmissionFile.objects.all()
    serializer_class = serializer_for(SubmissionFile)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        obj = self.get_object()
        return private_response(obj.file, obj.original_filename)
