"""Opt-in repeatable lab benchmark; never uses the application's data.

MEASURE_OUT=... pytest tests/benchmark_course.py -q -s
"""

import json
import os
import statistics
import time
from pathlib import Path

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.assignments.models import Assignment
from apps.courses.models import CourseVersion, Topic, Week
from apps.courses.services import duplicate, publish
from apps.enrollments.models import Enrollment
from apps.testing.models import AnswerOption, Question, Test


def test_large_course_metrics(world, client_for):
    version, course, teacher = world["version"], world["course"], world["teacher"]
    for number in range(2, 6):
        week = Week.objects.create(course_version=version, number=number, title=f"Week {number}")
        for index in range(8):
            topic = Topic.objects.create(
                week=week, title=f"Topic {index}", content="Қазақша / Русский / English. " * 60
            )
            Assignment.objects.create(topic=topic, title="Assignment", status="PUBLISHED")
            test = Test.objects.create(topic=topic, title="Test", status="PUBLISHED")
            for position in range(8):
                question = Question.objects.create(
                    test=test, text=f"Question {position}", type="SINGLE_CHOICE"
                )
                AnswerOption.objects.bulk_create(
                    [
                        AnswerOption(question=question, text=f"Option {i}", is_correct=i == 0)
                        for i in range(4)
                    ]
                )
    enrollments = [world["enrollment"]]
    for i in range(24):
        student = User.objects.create(
            username=f"measure-{i}",
            email=f"measure-{i}@example.test",
            role="STUDENT",
            owner_teacher=teacher,
            must_change_password=False,
        )
        enrollments.append(
            Enrollment.objects.create(
                student=student,
                course=course,
                course_version=version,
                assigned_by=teacher,
                source_type="INDIVIDUAL",
            )
        )
    results = {
        "database": connection.vendor,
        "dataset": {"topics": 33, "questions": 257, "options": 1026, "enrollments": 25},
        "samples": 7,
    }

    def measure(name, operation):
        observations = []
        operation()  # warm database/query paths; not browser cache
        for _ in range(7):
            with CaptureQueriesContext(connection) as queries:
                started = time.perf_counter()
                payload = operation()
                elapsed = (time.perf_counter() - started) * 1000
            observations.append(
                {"ms": round(elapsed, 2), "queries": len(queries), "bytes": payload}
            )
        times = sorted(item["ms"] for item in observations)
        results[name] = {
            "p50_ms": statistics.median(times),
            "p95_ms": times[-1],
            "observations": observations,
        }

    def tree(role):
        response = client_for(world[role]).get(f"/api/v1/courses/{course.pk}/tree/")
        assert response.status_code == 200
        return len(response.content)

    def publishing():
        with transaction.atomic():
            CourseVersion.objects.filter(pk=version.pk).update(status="DRAFT")
            publish(version, teacher)
            transaction.set_rollback(True)
        return 0

    def copying():
        with transaction.atomic():
            duplicate(version, teacher)
            transaction.set_rollback(True)
        return 0

    def result_rows():
        client = client_for(teacher)
        total = 0
        for enrollment in enrollments:
            for action in ["progress", "grades"]:
                response = client.get(f"/api/v1/enrollments/{enrollment.pk}/{action}/")
                assert response.status_code == 200
                total += len(response.content)
        return total

    measure("student_tree", lambda: tree("student"))
    measure("editor_tree", lambda: tree("teacher"))
    measure("publish", publishing)
    measure("duplicate", copying)
    measure("results_25_rows", result_rows)
    target = Path(os.environ.get("MEASURE_OUT", "../.runtime/rc/backend-measure.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: {k: v for k, v in value.items() if k != "observations"}
                if isinstance(value, dict)
                else value
                for key, value in results.items()
            }
        )
    )
