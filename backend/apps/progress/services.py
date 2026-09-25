from django.utils import timezone

from apps.assignments.models import Submission
from apps.courses.models import Topic
from apps.testing.models import TestAttempt

from .models import StudentProgress, TopicProgress


def summary(enrollment, persist=False):
    version = enrollment.course_version
    topics = list(
        Topic.objects.filter(week__course_version=version).prefetch_related(
            "materials", "assignments", "tests"
        )
    )
    materials_done = set(
        StudentProgress.objects.filter(enrollment=enrollment).values_list("material_id", flat=True)
    )
    assignments_done = set(
        Submission.objects.filter(
            student=enrollment.student, assignment__topic__week__course_version=version
        )
        .exclude(status="DRAFT")
        .values_list("assignment_id", flat=True)
    )
    tests_done = set(
        TestAttempt.objects.filter(
            student=enrollment.student,
            test__topic__week__course_version=version,
            status__in=["GRADED", "EXPIRED"],
        ).values_list("test_id", flat=True)
    )
    done = total = 0
    topic_reads = set(
        TopicProgress.objects.filter(enrollment=enrollment).values_list("topic_id", flat=True)
    )
    completed_topics = []
    for topic in topics:
        checks = [m.pk in materials_done for m in topic.materials.all() if m.is_required]
        checks += [a.pk in assignments_done for a in topic.assignments.all() if a.is_required]
        checks += [t.pk in tests_done for t in topic.tests.all() if t.is_required]
        if topic.content.strip():
            checks.append(topic.pk in topic_reads)
        if checks and all(checks):
            completed_topics.append(str(topic.pk))
        if topic.is_required:
            total += len(checks)
            done += sum(checks)
    progress = round(done * 100 / total, 2) if total else 0
    if persist and enrollment.status not in ["ARCHIVED", "FAILED"]:
        if not enrollment.started_at:
            enrollment.started_at = timezone.now()
        enrollment.status = "COMPLETED" if total and done == total else "IN_PROGRESS"
        enrollment.completed_at = timezone.now() if enrollment.status == "COMPLETED" else None
        enrollment.save()
    return {
        "percent": progress,
        "completed": done,
        "total": total,
        "completed_topics": completed_topics,
        "read_topics": [str(x) for x in topic_reads],
        "materials": [str(x) for x in materials_done],
        "assignments": [str(x) for x in assignments_done],
        "tests": [str(x) for x in tests_done],
    }
