from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import record, selected_fields
from apps.common.api import ScopedViewSet, lookup, representation
from apps.common.filters import CourseFilter
from apps.common.inputs import (
    DeleteDraftInput,
    EmptyInput,
    GradingWeightsInput,
    StudentInput,
    UpgradeStudentsInput,
    VersionInput,
    validated,
)
from apps.common.permissions import is_admin, is_teacher
from apps.common.read_contracts import AuthorWeekOutput, StudentWeekOutput
from apps.common.scope import editable, visible
from apps.common.serializers import serializer_for
from apps.courses.models import Course, Topic
from apps.courses.services import duplicate, new_version, publish
from apps.enrollments.models import Enrollment, GroupCourseAssignment
from apps.enrollments.services import enroll
from apps.grading.models import GradingComponent, GradingScheme
from apps.progress.models import TopicProgress
from apps.progress.services import summary


class CourseViewSet(ScopedViewSet):
    queryset = Course.objects.all()
    serializer_class = serializer_for(Course, ["current_version"])
    filterset_class = CourseFilter
    ordering_fields = ["created_at", "updated_at", "title"]

    @transaction.atomic
    def perform_create(self, serializer):
        self.validate_write(serializer)
        teacher = serializer.validated_data.get("teacher", self.request.user)
        discipline = serializer.validated_data["discipline"]
        if (
            teacher.role != "TEACHER"
            or (not is_admin(self.request.user) and teacher != self.request.user)
            or not discipline.teachers.filter(pk=teacher.pk).exists()
            or discipline.status != "ACTIVE"
        ):
            raise ValidationError("Дисциплина должна быть назначена преподавателю.")
        course = serializer.save(teacher=teacher)
        new_version(course, self.request.user)
        record(self.request.user, "content.created", course, new=selected_fields(course))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def restore(self, request, pk=None):
        validated(request, EmptyInput)
        if not is_teacher(request.user):
            raise PermissionDenied()
        obj = Course.objects.select_for_update().get(pk=self.get_object().pk)
        if obj.status == "ARCHIVED":
            if obj.discipline.status != "ACTIVE":
                raise ValidationError("Сначала восстановите дисциплину курса.")
            if obj.current_version_id and obj.current_version.status != "PUBLISHED":
                raise ValidationError("Проверьте опубликованную версию курса.")
            obj.status = "PUBLISHED" if obj.current_version_id else "DRAFT"
            obj.save(update_fields=["status", "updated_at"])
            record(
                request.user,
                "course.restored",
                obj,
                old={"status": "ARCHIVED"},
                new={"status": obj.status},
            )
        return Response(representation(obj, request))

    @extend_schema(request=VersionInput)
    @action(detail=True, methods=["post"], url_path="update-students-preview")
    def update_students_preview(self, request, pk=None):
        from .upgrades import upgrade_students

        data = validated(request, VersionInput)
        return Response(upgrade_students(request.user, self.get_object(), data["version"]))

    @extend_schema(request=UpgradeStudentsInput)
    @action(detail=True, methods=["post"], url_path="update-students")
    def update_students(self, request, pk=None):
        from .upgrades import upgrade_students

        data = validated(request, UpgradeStudentsInput)
        return Response(
            upgrade_students(
                request.user,
                self.get_object(),
                data["version"],
                apply=True,
                confirm_grading_change=data["confirm_grading_change"],
            )
        )

    @action(detail=True, methods=["post"], url_path="edit-draft")
    @transaction.atomic
    def edit_draft(self, request, pk=None):
        data = validated(request, VersionInput)
        if not is_teacher(request.user):
            raise PermissionDenied()
        course = Course.objects.select_for_update().get(pk=self.get_object().pk)
        if course.status == "ARCHIVED":
            raise ValidationError("Сначала восстановите курс из архива.")
        source = get_object_or_404(course.versions, pk=data["version"], status="PUBLISHED")
        # Keep assigned versions immutable, including historical/revoked assignments.
        if (
            not source.enrollments.exists()
            and not GroupCourseAssignment.objects.filter(course_version=source).exists()
        ):
            source.status = "DRAFT"
            source.published_at = None
            source.save(update_fields=["status", "published_at", "updated_at"])
            if course.current_version_id == source.pk:
                course.current_version = (
                    course.versions.filter(status="PUBLISHED")
                    .exclude(pk=source.pk)
                    .order_by("-version_number")
                    .first()
                )
                course.status = "PUBLISHED" if course.current_version_id else "DRAFT"
                course.save(update_fields=["current_version", "status", "updated_at"])
            record(
                request.user,
                "course.version_unpublished",
                source,
                old={"status": "PUBLISHED"},
                new={"status": "DRAFT"},
            )
            return Response(representation(source, request))
        draft = (
            course.versions.filter(status__in=["DRAFT", "REVIEW"])
            .order_by("-version_number")
            .first()
        )
        if draft is None:
            draft = duplicate(source, request.user)
        return Response(representation(draft, request))

    @action(detail=True, methods=["post"], url_path="delete-draft")
    @transaction.atomic
    def delete_draft(self, request, pk=None):
        data = validated(request, DeleteDraftInput)
        if not is_teacher(request.user):
            raise PermissionDenied()
        course = Course.objects.select_for_update().get(pk=self.get_object().pk)
        version = get_object_or_404(course.versions.select_for_update(), pk=data["version"])
        if version.status not in ["DRAFT", "REVIEW"] or course.current_version_id == version.pk:
            raise ValidationError("Опубликованную версию удалять нельзя.")
        expected = f"{course.title} · v{version.version_number}"
        if data["confirmation"] != expected:
            raise ValidationError({"confirmation": "Введите точное название и номер версии."})
        remaining = course.versions.exclude(pk=version.pk).order_by("-version_number").first()
        if remaining is None and course.status != "DRAFT":
            raise ValidationError("Последнюю версию этого курса удалять нельзя.")
        record(
            request.user,
            "course.draft_deleted",
            version,
            old={
                "course": str(course.pk),
                "version_number": version.version_number,
                "title": course.title,
            },
        )
        try:
            with transaction.atomic():
                version.delete()
                if remaining is None:
                    course.delete()
        except ProtectedError:
            raise ValidationError(
                "Черновик связан с назначениями, работами или AI-историей. Удаление запрещено; используйте архив курса."
            ) from None
        return Response(
            {
                "course_deleted": remaining is None,
                "next_version": str(remaining.pk) if remaining else None,
            }
        )

    @extend_schema(request=DeleteDraftInput)
    @action(detail=True, methods=["post"], url_path="delete-published")
    @transaction.atomic
    def delete_published(self, request, pk=None):
        data = validated(request, DeleteDraftInput)
        if not is_teacher(request.user):
            raise PermissionDenied()
        course = Course.objects.select_for_update().get(pk=self.get_object().pk)
        version = get_object_or_404(
            course.versions.select_for_update(), pk=data["version"], status="PUBLISHED"
        )
        if data["confirmation"] != f"{course.title} · v{version.version_number}":
            raise ValidationError({"confirmation": "Введите точное название и номер версии."})
        if (
            version.enrollments.exists()
            or GroupCourseAssignment.objects.filter(course_version=version).exists()
        ):
            raise ValidationError(
                "Эта версия связана с назначениями студентов или групп. Удаление уничтожило бы учебную историю. Для изменения используйте редактирование, для закрытия курса — архив."
            )
        remaining = course.versions.exclude(pk=version.pk).order_by("-version_number").first()
        try:
            with transaction.atomic():
                if course.current_version_id == version.pk:
                    course.current_version = (
                        course.versions.filter(status="PUBLISHED")
                        .exclude(pk=version.pk)
                        .order_by("-version_number")
                        .first()
                    )
                    if course.status != "ARCHIVED":
                        course.status = "PUBLISHED" if course.current_version_id else "DRAFT"
                    course.save(update_fields=["current_version", "status", "updated_at"])
                record(
                    request.user,
                    "course.published_version_deleted",
                    version,
                    old={
                        "course": str(course.pk),
                        "version_number": version.version_number,
                        "title": course.title,
                    },
                )
                version.delete()
                if remaining is None:
                    course.delete()
        except ProtectedError:
            raise ValidationError(
                "Версия связана с работами, прогрессом или AI-историей. Удаление запрещено; используйте архив курса."
            ) from None
        return Response(
            {
                "course_deleted": remaining is None,
                "next_version": str(remaining.pk) if remaining else None,
            }
        )

    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        if not is_teacher(request.user):
            raise PermissionDenied()
        course = self.get_object()
        kind = request.query_params.get("kind", "students")
        if kind == "students":
            rows = (
                Enrollment.objects.filter(course=course)
                .select_related("student", "course_version")
                .order_by("assigned_at", "pk")
            )
            field = "student_id"
        elif kind == "groups":
            rows = (
                GroupCourseAssignment.objects.filter(course=course, status="ACTIVE")
                .select_related("group", "course_version")
                .order_by("assigned_at", "pk")
            )
            field = "group_id"
        else:
            raise ValidationError({"kind": "Use students or groups."})
        selected = request.query_params.get("selected")
        if selected:
            from rest_framework import serializers

            selected = serializers.UUIDField().run_validation(selected)
        assigned = rows.filter(**{field: selected}).exists() if selected else False
        page = self.paginate_queryset(rows)
        result = []
        for row in page:
            recipient = row.student if kind == "students" else row.group
            result.append(
                {
                    "id": str(row.pk),
                    "recipient_id": str(recipient.pk),
                    "name": (recipient.get_full_name() or recipient.email)
                    if kind == "students"
                    else recipient.name,
                    "status": row.status,
                    "version_number": row.course_version.version_number,
                    "access_revoked": getattr(row, "access_revoked", False),
                }
            )
        response = self.get_paginated_response(result)
        response.data["selected_assigned"] = assigned
        return response

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        course = self.get_object()
        return Response(
            [representation(v, request) for v in visible(course.versions.all(), request.user)]
        )

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        data = validated(request, VersionInput)
        course = self.get_object()
        version = get_object_or_404(course.versions, pk=data["version"])
        return Response(representation(publish(version, request.user), request))

    @extend_schema(request=GradingWeightsInput)
    @action(detail=True, methods=["post"], url_path="grading-weights")
    @transaction.atomic
    def grading_weights(self, request, pk=None):
        data = validated(request, GradingWeightsInput)
        course = Course.objects.select_for_update().get(pk=self.get_object().pk)
        version = get_object_or_404(course.versions.select_for_update(), pk=data["version"])
        editable(version, request.user)
        scheme, _ = GradingScheme.objects.get_or_create(course_version=version)
        old = dict(scheme.components.values_list("kind", "weight"))
        weights = {kind: weight for kind, weight in data["weights"].items() if weight}
        scheme.components.exclude(kind__in=weights).delete()
        for kind, weight in weights.items():
            GradingComponent.objects.update_or_create(
                scheme=scheme, kind=kind, defaults={"weight": weight}
            )
        record(request.user, "course.grading_updated", scheme, old=old, new=weights)
        return Response([representation(c, request) for c in scheme.components.all()])

    @action(detail=True, methods=["post"], url_path="grading-preset")
    @transaction.atomic
    def grading_preset(self, request, pk=None):
        from apps.assignments.models import Assignment
        from apps.testing.models import Test

        data = validated(request, VersionInput)

        course = self.get_object()
        Course.objects.select_for_update().get(pk=course.pk)
        version = get_object_or_404(course.versions.select_for_update(), pk=data["version"])
        editable(version, request.user)
        kinds = []
        if Assignment.objects.filter(topic__week__course_version=version).exists():
            kinds.append("ASSIGNMENTS")
        tests = Test.objects.filter(topic__week__course_version=version)
        for kind, final in [("TESTS", False), ("FINAL", True)]:
            if tests.filter(is_final=final).exists():
                kinds.append(kind)
        if not kinds:
            raise ValidationError("Сначала добавьте задание или тест.")
        scheme, _ = GradingScheme.objects.get_or_create(course_version=version)
        # Retry safely without replacing any weights already chosen by the author.
        if not scheme.components.exists():
            base, remainder = divmod(100, len(kinds))
            for index, kind in enumerate(kinds):
                GradingComponent.objects.create(
                    scheme=scheme, kind=kind, weight=base + (index < remainder)
                )
            record(request.user, "course.grading_configured", scheme)
        return Response([representation(c, request) for c in scheme.components.all()])

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        data = validated(request, VersionInput)
        course = self.get_object()
        if not is_teacher(request.user):
            raise PermissionDenied()
        version = get_object_or_404(course.versions, pk=data["version"])
        return Response(representation(duplicate(version, request.user), request), status=201)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        data = validated(request, StudentInput)
        if not is_teacher(request.user):
            raise PermissionDenied()
        obj = enroll(request.user, lookup(User, data["student"], request.user), self.get_object())
        return Response(representation(obj, request))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def archive(self, request, pk=None):
        validated(request, EmptyInput)
        obj = self.get_object()
        if not is_teacher(request.user):
            raise PermissionDenied()
        obj = Course.objects.select_for_update().get(pk=obj.pk)
        obj.status = "ARCHIVED"
        obj.save()
        record(request.user, "course.archived", obj)
        return Response(representation(obj, request))

    @action(detail=True, methods=["get"])
    def tree(self, request, pk=None):
        course = self.get_object()
        if is_teacher(request.user):
            version = (
                get_object_or_404(course.versions, pk=request.query_params["version"])
                if request.query_params.get("version")
                else course.versions.order_by("-version_number").first()
            )
        else:
            version = get_object_or_404(
                Enrollment, student=request.user, course=course
            ).course_version
        if not version:
            raise ValidationError("Нет версии курса.")
        author = is_teacher(request.user)
        relations = ["topics__materials", "topics__assignments", "topics__tests"]
        if author:
            relations.append("topics__tests__questions__options")
        week_output = AuthorWeekOutput if author else StudentWeekOutput
        weeks = week_output(
            version.weeks.prefetch_related(*relations), many=True, context={"request": request}
        ).data
        scheme = GradingScheme.objects.filter(course_version=version).first()
        return Response(
            {
                "course": representation(course, request),
                "version": representation(version, request),
                "weeks": weeks,
                "scheme": representation(scheme, request) if scheme else None,
                "components": [representation(c, request) for c in scheme.components.all()]
                if scheme
                else [],
            }
        )


class TopicViewSet(ScopedViewSet):
    queryset = Topic.objects.all()
    serializer_class = serializer_for(Topic)
    filterset_fields = ["week"]

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        validated(request, EmptyInput)
        if request.user.role != "STUDENT":
            raise PermissionDenied()
        topic = self.get_object()
        with transaction.atomic():
            enrollment = get_object_or_404(
                Enrollment.objects.select_for_update(),
                student=request.user,
                course_version=topic.week.course_version,
            )
            if enrollment.access_revoked:
                raise PermissionDenied("Доступ к курсу закрыт.")
            TopicProgress.objects.get_or_create(enrollment=enrollment, topic=topic)
            return Response(summary(enrollment, persist=True))
