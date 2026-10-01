"""One bounded read model for a page of enrollment results."""

from collections import defaultdict

from django.db.models import Max

from apps.assignments.models import Submission
from apps.courses.models import Topic
from apps.grading.models import GradingComponent
from apps.progress.models import StudentProgress, TopicProgress
from apps.testing.models import TestAttempt


class LearningReadModel:
    def __init__(self, enrollments, mode="both"):
        ids = [row.pk for row in enrollments]
        versions = {row.course_version_id for row in enrollments}
        students = {row.student_id for row in enrollments}
        self.topics, self.components = defaultdict(list), defaultdict(list)
        self.materials, self.read_topics = defaultdict(set), defaultdict(set)
        self.assignments, self.tests = defaultdict(set), defaultdict(set)
        self.assignment_scores, self.test_scores = defaultdict(dict), defaultdict(dict)
        for topic in (
            Topic.objects.filter(week__course_version_id__in=versions)
            .select_related("week")
            .prefetch_related(*(["materials"] if mode != "grades" else []), "assignments", "tests")
        ):
            self.topics[topic.week.course_version_id].append(topic)
        if mode != "progress":
            for component in GradingComponent.objects.filter(
                scheme__course_version_id__in=versions
            ).select_related("scheme"):
                self.components[component.scheme.course_version_id].append(component)
        if mode != "grades":
            for enrollment, material in StudentProgress.objects.filter(
                enrollment_id__in=ids
            ).values_list("enrollment_id", "material_id"):
                self.materials[enrollment].add(material)
            for enrollment, topic in TopicProgress.objects.filter(
                enrollment_id__in=ids
            ).values_list("enrollment_id", "topic_id"):
                self.read_topics[enrollment].add(topic)
        for row in (
            Submission.objects.filter(
                student_id__in=students, assignment__topic__week__course_version_id__in=versions
            )
            .order_by("assignment_id", "-attempt_number")
            .values(
                "student_id",
                "assignment_id",
                "assignment__topic__week__course_version_id",
                "status",
                "score",
            )
        ):
            key = (row["student_id"], row["assignment__topic__week__course_version_id"])
            self.assignments[key].add(row["assignment_id"])
            if row["status"] == "GRADED":
                self.assignment_scores[key].setdefault(row["assignment_id"], float(row["score"]))
        attempts = TestAttempt.objects.filter(
            student_id__in=students,
            test__topic__week__course_version_id__in=versions,
            status__in=["GRADED", "EXPIRED"],
        )
        for row in attempts.values(
            "student_id", "test_id", "test__topic__week__course_version_id"
        ).annotate(best=Max("score")):
            key = (row["student_id"], row["test__topic__week__course_version_id"])
            self.tests[key].add(row["test_id"])
            if row["best"] is not None:
                self.test_scores[key][row["test_id"]] = float(row["best"])
