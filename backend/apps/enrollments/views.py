from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.api import ReadOnlyScoped
from apps.common.filters import EnrollmentFilter
from apps.common.read_contracts import GradesOutput, ProgressOutput
from apps.common.serializers import serializer_for
from apps.enrollments.models import Enrollment
from apps.grading.services import grades
from apps.progress.services import summary

from .read_models import LearningReadModel


class EnrollmentDisplaySerializer(serializer_for(Enrollment)):
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta(serializer_for(Enrollment).Meta):
        fields = [*serializer_for(Enrollment).Meta.fields, "course_title", "student_name"]
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        return obj.student.get_full_name() or obj.student.email


class EnrollmentSummaryOutput(EnrollmentDisplaySerializer):
    progress = ProgressOutput()
    grades = GradesOutput()

    class Meta(EnrollmentDisplaySerializer.Meta):
        fields = [*EnrollmentDisplaySerializer.Meta.fields, "progress", "grades"]
        read_only_fields = fields


class EnrollmentViewSet(ReadOnlyScoped):
    queryset = Enrollment.objects.select_related("student", "course", "course_version")
    serializer_class = EnrollmentDisplaySerializer
    filterset_class = EnrollmentFilter

    @extend_schema(responses=EnrollmentSummaryOutput(many=True))
    @action(detail=False, methods=["get"])
    def summaries(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        data = LearningReadModel(page)
        return self.get_paginated_response(
            [
                {
                    **self.get_serializer(row).data,
                    "progress": summary(row, data=data),
                    "grades": grades(row, data=data),
                }
                for row in page
            ]
        )

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        return Response(summary(self.get_object()))

    @action(detail=True, methods=["get"])
    def grades(self, request, pk=None):
        return Response(grades(self.get_object()))
