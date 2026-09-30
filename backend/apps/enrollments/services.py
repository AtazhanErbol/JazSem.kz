from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.academics.models import GroupMembership, StudyGroup
from apps.accounts.models import User
from apps.audit.services import record
from apps.common.scope import require_visible
from apps.courses.models import Course
from apps.notifications.services import notify

from .models import Enrollment, EnrollmentSource, GroupCourseAssignment


@transaction.atomic
def enroll(actor, student, course, group_assignment=None):
    require_visible(course, actor)
    require_visible(student, actor)
    course = Course.objects.select_for_update().get(pk=course.pk)
    student = User.objects.select_for_update().get(pk=student.pk)
    if (
        student.role != "STUDENT"
        or not student.is_active
        or student.owner_teacher_id != course.teacher_id
    ):
        raise ValidationError("Студент должен принадлежать преподавателю курса.")
    version = group_assignment.course_version if group_assignment else course.current_version
    if version and version.course_id != course.pk:
        raise ValidationError("Версия не принадлежит курсу.")
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
        record(
            actor,
            "enrollment.created",
            enrollment,
            new={"course": str(course.pk), "version": str(version.pk), "student": str(student.pk)},
        )
        notify(student, "COURSE", course.title, link=f"/app/courses/{course.pk}", email=True)
    return enrollment


@transaction.atomic
def assign_group(actor, group, course):
    require_visible(group, actor)
    require_visible(course, actor)
    group = StudyGroup.objects.select_for_update().get(pk=group.pk)
    course = Course.objects.select_for_update().get(pk=course.pk)
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
    for membership in (
        group.memberships.filter(status="ACTIVE").select_related("student").order_by("student_id")
    ):
        enroll(actor, membership.student, course, assignment)
    record(
        actor,
        "group.course_assigned",
        assignment,
        new={"course": str(course.pk), "version": str(assignment.course_version_id)},
    )
    return assignment


@transaction.atomic
def add_member(actor, group, student):
    require_visible(group, actor)
    require_visible(student, actor)
    group = StudyGroup.objects.select_for_update().get(pk=group.pk)
    assignments = list(
        group.course_assignments.filter(status="ACTIVE")
        .select_related("course", "course_version")
        .order_by("course_id")
    )
    # Group -> every course (stable order) -> Student. Never acquire a new
    # course lock after taking the student lock during inheritance.
    list(
        Course.objects.select_for_update()
        .filter(pk__in=[a.course_id for a in assignments])
        .order_by("pk")
    )
    student = User.objects.select_for_update().get(pk=student.pk)
    if (
        student.role != "STUDENT"
        or not student.is_active
        or student.owner_teacher_id != group.teacher_id
        or group.status != "ACTIVE"
    ):
        raise ValidationError("Недопустимый участник группы.")
    membership, _ = GroupMembership.objects.get_or_create(
        group=group, student=student, status="ACTIVE"
    )
    record(
        actor,
        "group.member_added",
        membership,
        new={"group": str(group.pk), "student": str(student.pk)},
    )
    for assignment in assignments:
        enroll(actor, student, assignment.course, assignment)
    return membership
