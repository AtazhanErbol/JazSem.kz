from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.api import ReadOnlyScoped
from apps.common.serializers import serializer_for
from apps.enrollments.models import Enrollment
from apps.grading.services import grades
from apps.progress.services import summary


class EnrollmentDisplaySerializer(serializer_for(Enrollment)):
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta(serializer_for(Enrollment).Meta):
        fields = [*serializer_for(Enrollment).Meta.fields, "course_title", "student_name"]
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        return obj.student.get_full_name() or obj.student.email


class EnrollmentViewSet(ReadOnlyScoped):
    queryset = Enrollment.objects.select_related("student", "course", "course_version")
    serializer_class = EnrollmentDisplaySerializer
    filterset_fields = ["course", "student", "status"]

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        return Response(summary(self.get_object()))

    @action(detail=True, methods=["get"])
    def grades(self, request, pk=None):
        return Response(grades(self.get_object()))
