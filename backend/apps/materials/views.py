from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.common.api import ScopedViewSet, private_response
from apps.common.serializers import serializer_for
from apps.enrollments.models import Enrollment
from apps.materials.models import Material
from apps.progress.models import StudentProgress
from apps.progress.services import summary


class MaterialViewSet(ScopedViewSet):
    queryset = Material.objects.all()
    serializer_class = serializer_for(Material, ["original_filename"])
    throttle_scope = "upload"

    def get_throttles(self):
        return super().get_throttles() if self.action in ["create", "partial_update"] else []

    def perform_create(self, serializer):
        self.validate_write(serializer)
        file = serializer.validated_data.get("file")
        serializer.save(original_filename=file.name if file else "")

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        material = self.get_object()
        if not material.file:
            raise ValidationError("Файл отсутствует.")
        return private_response(material.file, material.original_filename)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        if request.user.role != "STUDENT":
            raise PermissionDenied()
        material = self.get_object()
        with transaction.atomic():
            enrollment = get_object_or_404(
                Enrollment.objects.select_for_update(),
                student=request.user,
                course_version=material.topic.week.course_version,
            )
            StudentProgress.objects.get_or_create(enrollment=enrollment, material=material)
            return Response(summary(enrollment, persist=True))
