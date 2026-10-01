import django_filters as filters
from django.utils import timezone

from apps.academics.models import GroupMembership
from apps.accounts.models import User
from apps.assignments.models import Assignment, Submission
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.testing.models import Test


class UserFilter(filters.FilterSet):
    group = filters.UUIDFilter(method="in_group")
    discipline = filters.UUIDFilter(field_name="disciplines")

    def in_group(self, qs, name, value):
        return qs.filter(
            pk__in=GroupMembership.objects.filter(group_id=value, status="ACTIVE").values(
                "student_id"
            )
        )

    class Meta:
        model = User
        fields = ["role", "is_active", "owner_teacher", "group", "discipline"]


class CourseFilter(filters.FilterSet):
    active = filters.BooleanFilter(method="active_courses")
    group = filters.UUIDFilter(field_name="groupcourseassignment__group", distinct=True)

    def active_courses(self, qs, name, value):
        return qs.exclude(status="ARCHIVED") if value else qs

    class Meta:
        model = Course
        fields = ["status", "discipline", "teacher", "group", "active"]


class AssignmentFilter(filters.FilterSet):
    course = filters.UUIDFilter(field_name="topic__week__course_version__course")
    teacher = filters.UUIDFilter(field_name="topic__week__course_version__course__teacher")
    due = filters.ChoiceFilter(
        choices=[("overdue", "Overdue"), ("future", "Future"), ("none", "No deadline")],
        method="deadline",
    )

    def deadline(self, qs, name, value):
        if value == "none":
            return qs.filter(deadline__isnull=True)
        return qs.filter(
            **{"deadline__lt" if value == "overdue" else "deadline__gte": timezone.now()}
        )

    class Meta:
        model = Assignment
        fields = ["status", "topic", "course", "teacher", "due"]


class TestFilter(filters.FilterSet):
    course = filters.UUIDFilter(field_name="topic__week__course_version__course")
    teacher = filters.UUIDFilter(field_name="topic__week__course_version__course__teacher")

    class Meta:
        model = Test
        fields = ["status", "topic", "course", "teacher"]


class SubmissionFilter(filters.FilterSet):
    course = filters.UUIDFilter(field_name="assignment__topic__week__course_version__course")
    group = filters.UUIDFilter(method="in_group")
    pending = filters.BooleanFilter(method="pending_review")

    def in_group(self, qs, name, value):
        return qs.filter(
            student_id__in=GroupMembership.objects.filter(group_id=value, status="ACTIVE").values(
                "student_id"
            )
        )

    def pending_review(self, qs, name, value):
        return qs.filter(status__in=["SUBMITTED", "RESUBMITTED", "UNDER_REVIEW"]) if value else qs

    class Meta:
        model = Submission
        fields = ["status", "assignment", "student", "course", "group", "pending"]


class EnrollmentFilter(filters.FilterSet):
    teacher = filters.UUIDFilter(field_name="course__teacher")
    group = filters.UUIDFilter(method="in_group")

    def in_group(self, qs, name, value):
        return qs.filter(
            student_id__in=GroupMembership.objects.filter(group_id=value, status="ACTIVE").values(
                "student_id"
            )
        )

    class Meta:
        model = Enrollment
        fields = ["course", "student", "status", "teacher", "group"]
