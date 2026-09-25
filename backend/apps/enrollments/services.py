from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.academics.models import GroupMembership, StudyGroup
from apps.accounts.models import User
from apps.common.scope import require_visible
from apps.notifications.services import notify

from .models import Enrollment, EnrollmentSource, GroupCourseAssignment


@transaction.atomic
def enroll(actor, student, course, group_assignment=None):
    require_visible(course, actor)
    require_visible(student, actor)
    User.objects.select_for_update().get(pk=student.pk)
    if (
        student.role != "STUDENT"
        or not student.is_active
        or student.created_by_id != course.teacher_id
    ):
        raise ValidationError("Студент должен принадлежать преподавателю курса.")
    version = group_assignment.course_version if group_assignment else course.current_version
    if course.status != "PUBLISHED" or not version or version.status != "PUBLISHED":
        raise ValidationError("Назначить можно только опубликованный курс.")
    enrollment, created = Enrollment.objects.get_or_create(
        student=student,
        course=course,
        defaults={
            "course_version": version,
            "assigned_by": actor,
            "source_type": "GROUP" if group_assignment else "INDIVIDUAL",
            "assigned_group": group_assignment.group if group_assignment else None,
        },
    )
    EnrollmentSource.objects.get_or_create(
        enrollment=enrollment,
        source_key=str(group_assignment.pk) if group_assignment else "INDIVIDUAL",
        defaults={"assigned_by": actor, "group_assignment": group_assignment},
    )
    if created:
        notify(student, "COURSE", course.title, link=f"/app/courses/{course.pk}")
    return enrollment


@transaction.atomic
def assign_group(actor, group, course):
    require_visible(group, actor)
    require_visible(course, actor)
    group = StudyGroup.objects.select_for_update().get(pk=group.pk)
    if (
        group.teacher_id != course.teacher_id
        or group.status != "ACTIVE"
        or course.status != "PUBLISHED"
    ):
        raise ValidationError("Проверьте преподавателя и статус курса/группы.")
    assignment, _ = GroupCourseAssignment.objects.update_or_create(
        group=group,
        course=course,
        defaults={
            "course_version": course.current_version,
            "assigned_by": actor,
            "status": "ACTIVE",
        },
    )
    for membership in group.memberships.filter(status="ACTIVE").select_related("student"):
        enroll(actor, membership.student, course, assignment)
    return assignment


@transaction.atomic
def add_member(actor, group, student):
    require_visible(group, actor)
    require_visible(student, actor)
    group = StudyGroup.objects.select_for_update().get(pk=group.pk)
    if (
        student.role != "STUDENT"
        or student.created_by_id != group.teacher_id
        or group.status != "ACTIVE"
    ):
        raise ValidationError("Недопустимый участник группы.")
    membership, _ = GroupMembership.objects.get_or_create(
        group=group, student=student, status="ACTIVE"
    )
    for assignment in group.course_assignments.filter(status="ACTIVE").select_related(
        "course", "course_version"
    ):
        enroll(actor, student, assignment.course, assignment)
    return membership
