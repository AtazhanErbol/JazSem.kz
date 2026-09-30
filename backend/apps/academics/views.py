from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.academics.models import Discipline, GroupMembership, StudyGroup
from apps.accounts.models import User
from apps.common.api import ScopedViewSet, lookup, representation
from apps.common.inputs import CourseInput, EmptyInput, StudentInput, validated
from apps.common.permissions import is_admin
from apps.common.serializers import serializer_for
from apps.courses.models import Course
from apps.enrollments.services import add_member, assign_group


class DisciplineViewSet(ScopedViewSet):
    queryset = Discipline.objects.all()
    serializer_class = serializer_for(Discipline, ["created_by"])
    search_fields = ["name", "code"]

    def validate_write(self, serializer):
        if not is_admin(self.request.user):
            raise PermissionDenied()
        super().validate_write(serializer)
        if any(u.role != "TEACHER" for u in serializer.validated_data.get("teachers", [])):
            raise ValidationError("Назначайте только преподавателей.")

    def perform_create(self, serializer):
        self.validate_write(serializer)
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        validated(request, EmptyInput)
        if not is_admin(request.user):
            raise PermissionDenied()
        obj = self.get_object()
        obj.status = "ARCHIVED"
        obj.save()
        return Response(representation(obj, request))


class GroupViewSet(ScopedViewSet):
    queryset = StudyGroup.objects.all()
    serializer_class = serializer_for(StudyGroup)
    search_fields = ["name"]
    filterset_fields = ["teacher", "status"]

    def perform_create(self, serializer):
        self.validate_write(serializer)
        teacher = serializer.validated_data.get("teacher", self.request.user)
        if teacher.role != "TEACHER" or (
            not is_admin(self.request.user) and teacher != self.request.user
        ):
            raise PermissionDenied()
        serializer.save(teacher=teacher)

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        group = self.get_object()
        if request.method == "POST":
            data = validated(request, StudentInput)
            obj = add_member(request.user, group, lookup(User, data["student"], request.user))
            return Response(representation(obj, request), status=201)
        return Response(
            [
                representation(m, request)
                for m in group.memberships.select_related("student").filter(status="ACTIVE")
            ]
        )

    @action(detail=True, methods=["post"], url_path="remove-member")
    def remove_member(self, request, pk=None):
        data = validated(request, StudentInput)
        member = get_object_or_404(
            GroupMembership,
            group=self.get_object(),
            student_id=data["student"],
            status="ACTIVE",
        )
        member.status = "LEFT"
        member.left_at = timezone.now()
        member.save()
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        data = validated(request, CourseInput)
        obj = assign_group(
            request.user,
            self.get_object(),
            lookup(Course, data["course"], request.user),
        )
        return Response(representation(obj, request))

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        validated(request, EmptyInput)
        group = self.get_object()
        group.status = "ARCHIVED"
        group.save()
        group.course_assignments.update(status="ARCHIVED")
        return Response(representation(group, request))
