from django.db.models import Max

from apps.assignments.models import Assignment, Submission
from apps.testing.models import Test, TestAttempt

from .models import GradingComponent


def grades(enrollment):
    version = enrollment.course_version
    results = []
    total = 0.0
    latest_scores = {}
    for row in (
        Submission.objects.filter(
            student_id=enrollment.student_id,
            assignment__topic__week__course_version=version,
            status="GRADED",
        )
        .order_by("assignment_id", "-attempt_number")
        .values("assignment_id", "score")
    ):
        latest_scores.setdefault(row["assignment_id"], float(row["score"]))
    assignment_scores = [
        latest_scores.get(pk, 0)
        for pk in Assignment.objects.filter(topic__week__course_version=version).values_list(
            "pk", flat=True
        )
    ]
    best_scores = dict(
        TestAttempt.objects.filter(
            student_id=enrollment.student_id,
            test__topic__week__course_version=version,
            status__in=["GRADED", "EXPIRED"],
            score__isnull=False,
        )
        .values("test_id")
        .annotate(best=Max("score"))
        .values_list("test_id", "best")
    )
    tests = list(Test.objects.filter(topic__week__course_version=version).values("pk", "is_final"))
    for component in GradingComponent.objects.filter(scheme__course_version=version):
        if component.kind == "ASSIGNMENTS":
            values = assignment_scores
        else:
            values = [
                float(best_scores.get(test["pk"], 0))
                for test in tests
                if test["is_final"] == (component.kind == "FINAL")
            ]
        score = sum(values) / len(values) if values else 0
        total += score * component.weight / 100
        results.append(
            {"kind": component.kind, "weight": component.weight, "score": round(score, 2)}
        )
    return {"score": round(total, 2), "components": results}
