from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.permissions import is_admin, is_teacher

CONTENT_PATHS = {
    "courses.courseversion": "course",
    "courses.week": "course_version__course",
    "courses.topic": "week__course_version__course",
    "materials.material": "topic__week__course_version__course",
    "assignments.assignment": "topic__week__course_version__course",
    "testing.test": "topic__week__course_version__course",
    "testing.question": "test__topic__week__course_version__course",
    "testing.answeroption": "question__test__topic__week__course_version__course",
    "grading.gradingscheme": "course_version__course",
    "grading.gradingcomponent": "scheme__course_version__course",
}


def visible(qs, user):
    label = qs.model._meta.label_lower
    if is_admin(user):
        return qs
    if label == "accounts.user":
        return (
            qs.filter(Q(pk=user.pk) | Q(created_by=user, role="STUDENT"))
            if is_teacher(user)
            else qs.filter(pk=user.pk)
        )
    if label == "academics.discipline":
        return (
            qs.filter(teachers=user)
            if is_teacher(user)
            else qs.filter(course__enrollments__student=user).distinct()
        )
    if label == "academics.studygroup":
        return qs.filter(teacher=user) if is_teacher(user) else qs.none()
    if label == "academics.groupmembership":
        return qs.filter(group__teacher=user) if is_teacher(user) else qs.none()
    if label == "courses.course":
        return (
            qs.filter(teacher=user)
            if is_teacher(user)
            else qs.filter(
                enrollments__student=user,
                enrollments__status__in=["ASSIGNED", "IN_PROGRESS", "COMPLETED"],
                status="PUBLISHED",
            ).distinct()
        )
    if label in CONTENT_PATHS:
        path = CONTENT_PATHS[label]
        if is_teacher(user):
            return qs.filter(**{path + "__teacher": user})
        version_path = path.removesuffix("__course") if path != "course" else ""
        prefix = version_path + "__" if version_path else ""
        return qs.filter(
            **{
                prefix + "enrollments__student": user,
                prefix + "enrollments__status__in": ["ASSIGNED", "IN_PROGRESS", "COMPLETED"],
                prefix + "status": "PUBLISHED",
                path + "__status": "PUBLISHED",
            }
        ).distinct()
    if label == "enrollments.enrollment":
        return qs.filter(course__teacher=user) if is_teacher(user) else qs.filter(student=user)
    if label == "assignments.submission":
        return (
            qs.filter(assignment__topic__week__course_version__course__teacher=user)
            if is_teacher(user)
            else qs.filter(student=user)
        )
    if label == "assignments.submissionfile":
        return (
            qs.filter(submission__assignment__topic__week__course_version__course__teacher=user)
            if is_teacher(user)
            else qs.filter(submission__student=user)
        )
    if label == "testing.testattempt":
        return (
            qs.filter(test__topic__week__course_version__course__teacher=user)
            if is_teacher(user)
            else qs.filter(student=user)
        )
    if label in ["ai.sourcedocument", "ai.aijob"]:
        return qs.filter(course__teacher=user) if is_teacher(user) else qs.none()
    if label == "ai.aicoursedraft":
        return qs.filter(job__course__teacher=user) if is_teacher(user) else qs.none()
    if label == "ai.documentchunk":
        return qs.filter(document__course__teacher=user) if is_teacher(user) else qs.none()
    if label == "notifications.notification":
        return qs.filter(recipient=user)
    if label == "cms.contentblock":
        return qs.filter(is_published=True)
    return qs.none()


def require_visible(obj, user):
    if not visible(type(obj).objects.all(), user).filter(pk=obj.pk).exists():
        raise PermissionDenied("Объект недоступен.")


def version_of(obj):
    label = obj._meta.label_lower
    if label not in CONTENT_PATHS:
        return None
    if label == "courses.courseversion":
        return obj
    current = obj
    for part in CONTENT_PATHS[label].split("__")[:-1]:
        current = getattr(current, part)
    return current


def editable(obj, user):
    if not is_teacher(user):
        raise PermissionDenied()
    require_visible(obj, user)
    version = version_of(obj)
    if version:
        from apps.courses.models import CourseVersion

        version = CourseVersion.objects.select_for_update().get(pk=version.pk)
    if version and version.status not in ["DRAFT", "REVIEW"]:
        raise ValidationError("Опубликованная версия неизменяема. Создайте копию.")
