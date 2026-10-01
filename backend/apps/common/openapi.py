from drf_spectacular.utils import OpenApiTypes, PolymorphicProxySerializer, extend_schema


def annotate_actions():
    # Input contracts are the same classes executed by the handlers.
    from apps.academics.models import Discipline, GroupMembership, StudyGroup
    from apps.academics.views import DisciplineViewSet, GroupViewSet, MemberOutput
    from apps.accounts import serializers as auth
    from apps.accounts import views as account
    from apps.ai import contracts as ai
    from apps.ai.views import DraftViewSet, JobViewSet, SourceViewSet
    from apps.assignments.models import Submission
    from apps.assignments.views import AssignmentViewSet, SubmissionFileViewSet, SubmissionViewSet
    from apps.common import inputs as inp
    from apps.common import read_contracts as out
    from apps.common.serializers import serializer_for
    from apps.courses.models import Course, CourseVersion
    from apps.courses.views import CourseViewSet, TopicViewSet
    from apps.enrollments.models import Enrollment, GroupCourseAssignment
    from apps.enrollments.views import EnrollmentViewSet
    from apps.grading.models import GradingComponent
    from apps.materials.views import MaterialViewSet
    from apps.notifications.models import Notification
    from apps.notifications.views import (
        MailDeliverySerializer,
        MailOutboxViewSet,
        NotificationViewSet,
    )
    from apps.testing.models import TestAttempt
    from apps.testing.views import AttemptViewSet, TestViewSet

    def mark(view, method, request, response, **kwargs):
        setattr(
            view,
            method,
            extend_schema(request=request, responses=response, **kwargs)(getattr(view, method)),
        )

    for method in ["publish", "duplicate"]:
        mark(CourseViewSet, method, inp.VersionInput, serializer_for(CourseVersion))
    mark(
        CourseViewSet,
        "grading_preset",
        inp.VersionInput,
        serializer_for(GradingComponent)(many=True),
    )
    mark(CourseViewSet, "assign", inp.StudentInput, serializer_for(Enrollment))
    mark(CourseViewSet, "archive", inp.EmptyInput, serializer_for(Course))
    mark(CourseViewSet, "versions", None, serializer_for(CourseVersion)(many=True))
    mark(
        CourseViewSet,
        "tree",
        None,
        PolymorphicProxySerializer(
            component_name="CourseTree",
            serializers=[out.StudentTreeOutput, out.AuthorTreeOutput],
            resource_type_field_name=None,
        ),
    )
    mark(GroupViewSet, "assign", inp.CourseInput, serializer_for(GroupCourseAssignment))
    mark(
        GroupViewSet, "members", inp.StudentInput, serializer_for(GroupMembership), methods=["POST"]
    )
    mark(GroupViewSet, "members", None, MemberOutput(many=True), methods=["GET"])
    mark(GroupViewSet, "remove_member", inp.StudentInput, {204: None})
    mark(GroupViewSet, "archive", inp.EmptyInput, serializer_for(StudyGroup))
    mark(DisciplineViewSet, "archive", inp.EmptyInput, serializer_for(Discipline))
    mark(AssignmentViewSet, "submit", inp.SubmissionInput, {201: serializer_for(Submission)})
    for method, contract in [
        ("grade", inp.GradeInput),
        ("revision", inp.RevisionInput),
        ("review", inp.ReviewInput),
    ]:
        mark(SubmissionViewSet, method, contract, serializer_for(Submission))
    mark(SubmissionViewSet, "files", None, out.FileOutput(many=True))
    mark(AttemptViewSet, "answer", inp.AnswerInput, out.SavedOutput)
    mark(AttemptViewSet, "finish", inp.EmptyInput, serializer_for(TestAttempt))
    mark(AttemptViewSet, "retrieve", None, out.AttemptDetailOutput)
    mark(TestViewSet, "start", inp.EmptyInput, serializer_for(TestAttempt))
    mark(JobViewSet, "create", ai.GenerationInput, {202: ai.JobOutput})
    mark(JobViewSet, "cancel", inp.EmptyInput, ai.JobOutput)
    mark(JobViewSet, "draft", None, ai.DraftOutput)
    mark(SourceViewSet, "create", ai.SourceInput, {201: ai.SourceOutput})
    for method in ["retry", "exclude"]:
        mark(SourceViewSet, method, inp.EmptyInput, ai.SourceOutput)
    mark(SourceViewSet, "chunks", None, ai.ChunkOutput(many=True))
    mark(DraftViewSet, "partial_update", ai.DraftInput, ai.DraftOutput)
    mark(DraftViewSet, "regenerate", ai.RegenerateInput, {202: ai.JobOutput})
    mark(DraftViewSet, "confirm", inp.EmptyInput, serializer_for(CourseVersion))
    mark(EnrollmentViewSet, "progress", None, out.ProgressOutput)
    mark(EnrollmentViewSet, "grades", None, out.GradesOutput)
    for view in [TopicViewSet, MaterialViewSet]:
        mark(view, "complete", inp.EmptyInput, out.ProgressOutput)
    mark(NotificationViewSet, "read", inp.EmptyInput, serializer_for(Notification))
    mark(MailOutboxViewSet, "retry", inp.EmptyInput, MailDeliverySerializer)
    mark(MailOutboxViewSet, "metrics", None, out.MailMetricsOutput)
    mark(account.AuthView, "get", None, out.CSRFOutput)
    mark(account.AuthView, "post", auth.LoginSerializer, auth.UserSerializer)
    mark(account.MeView, "patch", auth.ProfileInput, auth.UserSerializer)
    mark(account.ChangePasswordView, "post", auth.ChangePasswordInput, auth.UserSerializer)
    mark(account.ForgotView, "post", auth.EmailSerializer, out.MessageOutput)
    mark(account.ResetView, "post", auth.ResetPasswordInput, out.MessageOutput)
    mark(account.LogoutView, "post", inp.EmptyInput, {204: None})
    mark(account.UserViewSet, "deactivate", inp.EmptyInput, {204: None})
    for view in [MaterialViewSet, SubmissionFileViewSet, SourceViewSet]:
        mark(view, "download", None, OpenApiTypes.BINARY)
    for view, method in [
        (CourseViewSet, "versions"),
        (CourseViewSet, "grading_preset"),
        (GroupViewSet, "members"),
        (SubmissionViewSet, "files"),
    ]:
        getattr(view, method).kwargs["pagination_class"] = None
