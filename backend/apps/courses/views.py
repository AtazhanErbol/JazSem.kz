from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import record
from apps.common.api import ScopedViewSet, lookup, representation
from apps.common.inputs import EmptyInput, StudentInput, VersionInput, validated
from apps.common.permissions import is_admin, is_teacher
from apps.common.scope import editable, visible
from apps.common.serializers import serializer_for
from apps.courses.models import Course, Topic
from apps.courses.services import duplicate, new_version, publish
from apps.enrollments.models import Enrollment
from apps.enrollments.services import enroll
from apps.grading.models import GradingComponent, GradingScheme
from apps.progress.models import TopicProgress
from apps.progress.services import summary


class CourseViewSet(ScopedViewSet):
    queryset = Course.objects.all()
    serializer_class = serializer_for(Course, ["current_version"])
    filterset_fields = ["status", "discipline"]
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
        weeks = []
        for week in version.weeks.prefetch_related(
            "topics__materials", "topics__assignments", "topics__tests__questions__options"
        ):
            data = representation(week, request)
            data["topics"] = []
            for topic in week.topics.all():
                entry = representation(topic, request)
                for key in ["materials", "assignments", "tests"]:
                    entry[key] = [representation(x, request) for x in getattr(topic, key).all()]
                if is_teacher(request.user):
                    for test_data, test in zip(entry["tests"], topic.tests.all()):
                        test_data["questions"] = [
                            {
                                **representation(q, request),
                                "options": [representation(o, request) for o in q.options.all()],
                            }
                            for q in test.questions.all()
                        ]
                data["topics"].append(entry)
            weeks.append(data)
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
            TopicProgress.objects.get_or_create(enrollment=enrollment, topic=topic)
            return Response(summary(enrollment, persist=True))
