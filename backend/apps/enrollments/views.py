from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.api import ReadOnlyScoped
from apps.common.serializers import serializer_for
from apps.enrollments.models import Enrollment
from apps.grading.services import grades
from apps.progress.services import summary


class EnrollmentViewSet(ReadOnlyScoped):
    queryset = Enrollment.objects.select_related("student", "course", "course_version")
    serializer_class = serializer_for(Enrollment)
    filterset_fields = ["course", "student", "status"]

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        return Response(summary(self.get_object()))

    @action(detail=True, methods=["get"])
    def grades(self, request, pk=None):
        return Response(grades(self.get_object()))
