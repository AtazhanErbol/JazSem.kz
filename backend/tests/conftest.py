import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.academics.models import Discipline, StudyGroup
from apps.accounts.models import User
from apps.assignments.models import Assignment
from apps.courses.models import Course, Topic, Week
from apps.courses.services import new_version, publish
from apps.enrollments.services import enroll
from apps.grading.models import GradingComponent, GradingScheme
from apps.materials.models import Material
from apps.testing.models import AnswerOption, Question, Test


@pytest.fixture
def world(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    admin = User.objects.create_user(
        username="admin",
        email="admin@example.test",
        password="Example-pass-583!",
        role="ADMIN",
        must_change_password=False,
    )
    teacher = User.objects.create_user(
        username="teacher",
        email="teacher@example.test",
        password="Example-pass-583!",
        role="TEACHER",
        must_change_password=False,
    )
    other = User.objects.create_user(
        username="other",
        email="other@example.test",
        password="Example-pass-583!",
        role="TEACHER",
        must_change_password=False,
    )
    student = User.objects.create_user(
        username="student",
        email="student@example.test",
        password="Example-pass-583!",
        role="STUDENT",
        created_by=teacher,
        must_change_password=False,
    )
    outsider = User.objects.create_user(
        username="outsider",
        email="outsider@example.test",
        password="Example-pass-583!",
        role="STUDENT",
        created_by=other,
        must_change_password=False,
    )
    discipline = Discipline.objects.create(name="Mathematics", code="MATH", created_by=admin)
    discipline.teachers.add(teacher)
    course = Course.objects.create(
        discipline=discipline, teacher=teacher, title="Summer mathematics"
    )
    version = new_version(course, teacher)
    week = Week.objects.create(course_version=version, number=1, title="Algebra")
    topic = Topic.objects.create(week=week, title="Equations")
    material = Material.objects.create(
        topic=topic,
        title="Notes",
        type="FILE",
        file=SimpleUploadedFile("notes.txt", b"Equation notes", content_type="text/plain"),
        original_filename="notes.txt",
    )
    assignment = Assignment.objects.create(
        topic=topic, title="Solve the equation", instructions="Solve x + 1 = 2"
    )
    test = Test.objects.create(topic=topic, title="Quiz", max_attempts=2)
    question = Question.objects.create(test=test, text="1+1?", type="SINGLE_CHOICE")
    correct = AnswerOption.objects.create(question=question, text="2", is_correct=True)
    wrong = AnswerOption.objects.create(question=question, text="3")
    scheme = GradingScheme.objects.create(course_version=version)
    GradingComponent.objects.create(scheme=scheme, kind="ASSIGNMENTS", weight=50)
    GradingComponent.objects.create(scheme=scheme, kind="TESTS", weight=50)
    version = publish(version, teacher)
    course.refresh_from_db()
    assignment.refresh_from_db()
    test.refresh_from_db()
    enrollment = enroll(teacher, student, course)
    group = StudyGroup.objects.create(name="Summer group", teacher=teacher)
    return locals()


@pytest.fixture
def client_for():
    def make(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    return make
