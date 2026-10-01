def grades(enrollment, data=None):
    from apps.enrollments.read_models import LearningReadModel

    data = data or LearningReadModel([enrollment], mode="grades")
    key = (enrollment.student_id, enrollment.course_version_id)
    topics = data.topics[enrollment.course_version_id]
    results = []
    total = 0.0
    assignment_scores = [
        data.assignment_scores[key].get(a.pk, 0)
        for topic in topics
        for a in topic.assignments.all()
    ]
    best_scores = data.test_scores[key]
    tests = [
        {"pk": test.pk, "is_final": test.is_final} for topic in topics for test in topic.tests.all()
    ]
    for component in data.components[enrollment.course_version_id]:
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
