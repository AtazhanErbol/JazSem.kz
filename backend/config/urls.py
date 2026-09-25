from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from apps.academics.models import StudyGroup
from apps.academics.views import DisciplineViewSet, GroupViewSet
from apps.accounts.models import User
from apps.accounts.views import (
    AuthView,
    ChangePasswordView,
    ForgotView,
    LogoutView,
    MeView,
    ResetView,
    UserViewSet,
)
from apps.ai.views import ChunkViewSet, DraftViewSet, JobViewSet, SourceViewSet, UsageViewSet
from apps.assignments.models import Submission
from apps.assignments.views import AssignmentViewSet, SubmissionFileViewSet, SubmissionViewSet
from apps.audit.views import AuditViewSet
from apps.cms.views import ContentViewSet, PublicContentViewSet
from apps.common.api import content_view
from apps.common.openapi import annotate_actions
from apps.common.scope import visible
from apps.courses.models import Course, Week
from apps.courses.views import CourseViewSet, TopicViewSet
from apps.enrollments.models import Enrollment
from apps.enrollments.views import EnrollmentViewSet
from apps.grading.models import GradingComponent, GradingScheme
from apps.materials.views import MaterialViewSet
from apps.notifications.views import NotificationViewSet
from apps.testing.models import AnswerOption, Question
from apps.testing.views import AttemptViewSet, TestViewSet

annotate_actions()
router = DefaultRouter()
for prefix, view in [
    ("users", UserViewSet),
    ("disciplines", DisciplineViewSet),
    ("groups", GroupViewSet),
    ("courses", CourseViewSet),
    ("weeks", content_view(Week)),
    ("topics", TopicViewSet),
    ("materials", MaterialViewSet),
    ("assignments", AssignmentViewSet),
    ("submissions", SubmissionViewSet),
    ("submission-files", SubmissionFileViewSet),
    ("tests", TestViewSet),
    ("questions", content_view(Question)),
    ("options", content_view(AnswerOption)),
    ("attempts", AttemptViewSet),
    ("enrollments", EnrollmentViewSet),
    ("grading-schemes", content_view(GradingScheme)),
    ("grading-components", content_view(GradingComponent)),
    ("notifications", NotificationViewSet),
    ("audit", AuditViewSet),
    ("content", ContentViewSet),
    ("public-content", PublicContentViewSet),
    ("sources", SourceViewSet),
    ("chunks", ChunkViewSet),
    ("ai-jobs", JobViewSet),
    ("ai-drafts", DraftViewSet),
    ("ai-usage", UsageViewSet),
]:
    router.register(prefix, view, basename=prefix)


class DashboardView(APIView):
    class Output(serializers.Serializer):
        courses = serializers.IntegerField()
        students = serializers.IntegerField()
        teachers = serializers.IntegerField()
        groups = serializers.IntegerField()
        enrollments = serializers.IntegerField()
        review = serializers.IntegerField()

    serializer_class = Output

    def get(self, request):
        return Response(
            {
                name: visible(model.objects.all(), request.user).filter(**filters).count()
                for name, model, filters in [
                    ("courses", Course, {}),
                    ("students", User, {"role": "STUDENT"}),
                    ("teachers", User, {"role": "TEACHER"}),
                    ("groups", StudyGroup, {}),
                    ("enrollments", Enrollment, {}),
                    (
                        "review",
                        Submission,
                        {"status__in": ["SUBMITTED", "RESUBMITTED", "UNDER_REVIEW"]},
                    ),
                ]
            }
        )


def health(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        import redis
        from django.conf import settings

        redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2).ping()
        return JsonResponse({"status": "ready"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


urlpatterns = [
    path("health/", health),
    path("ready/", ready),
    path("api/v1/", include(router.urls)),
    path("api/v1/auth/login/", AuthView.as_view()),
    path("api/v1/auth/me/", MeView.as_view()),
    path("api/v1/auth/logout/", LogoutView.as_view()),
    path("api/v1/auth/change-password/", ChangePasswordView.as_view()),
    path("api/v1/auth/forgot-password/", ForgotView.as_view()),
    path("api/v1/auth/reset-password/", ResetView.as_view()),
    path("api/v1/dashboard/", DashboardView.as_view()),
    path("api/schema/", SpectacularAPIView.as_view()),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]
urlpatterns[-2].name = "schema"
