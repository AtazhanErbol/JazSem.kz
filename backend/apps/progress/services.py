from django.utils import timezone


def summary(enrollment, persist=False, data=None):
    from apps.enrollments.read_models import LearningReadModel

    data = data or LearningReadModel([enrollment], mode="progress")
    key = (enrollment.student_id, enrollment.course_version_id)
    topics = data.topics[enrollment.course_version_id]
    materials_done = data.materials[enrollment.pk]
    assignments_done = data.assignments[key]
    tests_done = data.tests[key]
    done = total = 0
    topic_reads = data.read_topics[enrollment.pk]
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
