from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.academics.models import Discipline, GroupMembership, StudyGroup
from apps.accounts.models import User
from apps.audit.services import record
from apps.common.api import ScopedViewSet, lookup, representation
from apps.common.inputs import CourseInput, EmptyInput, StudentInput, validated
from apps.common.permissions import is_admin
from apps.common.serializers import serializer_for
from apps.courses.models import Course
from apps.enrollments.services import add_member, assign_group


class MemberOutput(serializer_for(GroupMembership)):
    student_name = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source="student.email", read_only=True)

    def get_student_name(self, obj) -> str:
        return obj.student.get_full_name() or obj.student.email


class DisciplineViewSet(ScopedViewSet):
    queryset = Discipline.objects.all()
    serializer_class = serializer_for(Discipline, ["created_by"])
    search_fields = ["name", "code"]
    filterset_fields = ["status", "teachers"]

    def validate_write(self, serializer):
        if not is_admin(self.request.user):
            raise PermissionDenied()
        super().validate_write(serializer)
        if any(u.role != "TEACHER" for u in serializer.validated_data.get("teachers", [])):
            raise ValidationError("Назначайте только преподавателей.")

    def perform_create(self, serializer):
        self.validate_write(serializer)
        obj = serializer.save(created_by=self.request.user)
        record(
            self.request.user, "discipline.created", obj, new={"name": obj.name, "code": obj.code}
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        validated(request, EmptyInput)
        if not is_admin(request.user):
            raise PermissionDenied()
        obj = self.get_object()
        obj.status = "ARCHIVED"
        obj.save()
        record(request.user, "discipline.archived", obj)
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
        obj = serializer.save(teacher=teacher)
        record(
            self.request.user,
            "group.created",
            obj,
            new={"teacher": str(teacher.pk), "name": obj.name},
        )

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        group = self.get_object()
        if request.method == "POST":
            data = validated(request, StudentInput)
            obj = add_member(request.user, group, lookup(User, data["student"], request.user))
            return Response(representation(obj, request), status=201)
        return Response(
            MemberOutput(
                group.memberships.select_related("student").filter(status="ACTIVE"), many=True
            ).data
        )

    @action(detail=True, methods=["post"], url_path="remove-member")
    @transaction.atomic
    def remove_member(self, request, pk=None):
        data = validated(request, StudentInput)
        group = StudyGroup.objects.select_for_update().get(pk=self.get_object().pk)
        member = get_object_or_404(
            GroupMembership,
            group=group,
            student_id=data["student"],
            status="ACTIVE",
        )
        member.status = "LEFT"
        member.left_at = timezone.now()
        member.save()
        record(request.user, "group.member_removed", member, new={"status": "LEFT"})
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
    @transaction.atomic
    def archive(self, request, pk=None):
        validated(request, EmptyInput)
        group = StudyGroup.objects.select_for_update().get(pk=self.get_object().pk)
        group.status = "ARCHIVED"
        group.save()
        group.course_assignments.update(status="ARCHIVED")
        record(request.user, "group.archived", group)
        return Response(representation(group, request))
