from rest_framework.decorators import action
from rest_framework.response import Response

from apps.assignments.models import Assignment, Submission, SubmissionFile
from apps.assignments.services import review, submit
from apps.common.api import ReadOnlyScoped, ScopedViewSet, private_response, representation
from apps.common.serializers import serializer_for


class AssignmentViewSet(ScopedViewSet):
    queryset = Assignment.objects.all()
    serializer_class = serializer_for(Assignment)
    filterset_fields = ["status", "topic"]

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        obj = submit(
            self.get_object(),
            request.user,
            request.data.get("text_answer", ""),
            request.FILES.getlist("files"),
        )
        return Response(representation(obj, request), status=201)


class SubmissionViewSet(ReadOnlyScoped):
    queryset = Submission.objects.select_related("assignment", "student")
    serializer_class = serializer_for(Submission)
    filterset_fields = ["status", "assignment", "student"]
    search_fields = ["student__email", "assignment__title"]

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        return Response(
            representation(
                review(
                    self.get_object(),
                    request.user,
                    "grade",
                    request.data.get("score"),
                    request.data.get("comment", ""),
                ),
                request,
            )
        )

    @action(detail=True, methods=["post"], url_path="request-revision")
    def revision(self, request, pk=None):
        return Response(
            representation(
                review(
                    self.get_object(),
                    request.user,
                    "revision",
                    comment=request.data.get("comment", ""),
                ),
                request,
            )
        )

    @action(detail=True, methods=["post"], url_path="start-review")
    def review(self, request, pk=None):
        return Response(representation(review(self.get_object(), request.user, "review"), request))

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
