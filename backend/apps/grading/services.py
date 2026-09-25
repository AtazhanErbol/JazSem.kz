from apps.assignments.models import Assignment, Submission
from apps.testing.models import Test, TestAttempt

from .models import GradingComponent


def grades(enrollment):
    version = enrollment.course_version
    results = []
    total = 0.0
    for component in GradingComponent.objects.filter(scheme__course_version=version):
        values = []
        if component.kind == "ASSIGNMENTS":
            for assignment in Assignment.objects.filter(topic__week__course_version=version):
                latest = (
                    Submission.objects.filter(
                        assignment=assignment, student=enrollment.student, status="GRADED"
                    )
                    .order_by("-attempt_number")
                    .first()
                )
                values.append(float(latest.score) if latest else 0)
        else:
            for test in Test.objects.filter(
                topic__week__course_version=version, is_final=component.kind == "FINAL"
            ):
                best = (
                    TestAttempt.objects.filter(
                        test=test, student=enrollment.student, score__isnull=False
                    )
                    .order_by("-score")
                    .first()
                )
                values.append(float(best.score) if best else 0)
        score = sum(values) / len(values) if values else 0
        total += score * component.weight / 100
        results.append(
            {"kind": component.kind, "weight": component.weight, "score": round(score, 2)}
        )
    return {"score": round(total, 2), "components": results}
