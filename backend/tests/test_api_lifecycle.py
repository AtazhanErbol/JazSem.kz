from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import CourseVersion


def test_admin_teacher_student_lifecycle_through_api(world, client_for):
    admin = client_for(world["admin"])
    response = admin.post(
        "/api/v1/users/",
        {
            "email": "teacher2@example.test",
            "role": "TEACHER",
            "first_name": "Teacher",
            "last_name": "Two",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    teacher = User.objects.get(pk=response.data["id"])
    teacher.must_change_password = False
    teacher.save()
    client = client_for(teacher)
    response = client.post(
        "/api/v1/users/",
        {
            "email": "student2@example.test",
            "role": "STUDENT",
            "first_name": "Student",
            "last_name": "Two",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    student = User.objects.get(pk=response.data["id"])
    student.must_change_password = False
    student.save()
    discipline = admin.post(
        "/api/v1/disciplines/",
        {"name": "Physics", "code": "PHY", "teachers": [str(teacher.pk)]},
        format="json",
    )
    assert discipline.status_code == 201, discipline.data
    group = client.post(
        "/api/v1/groups/", {"name": "Physics group", "teacher": str(teacher.pk)}, format="json"
    )
    assert group.status_code == 201, group.data
    assert (
        client.post(
            f"/api/v1/groups/{group.data['id']}/members/",
            {"student": str(student.pk)},
            format="json",
        ).status_code
        == 201
    )
    course = client.post(
        "/api/v1/courses/",
        {
            "title": "Physics summer",
            "teacher": str(teacher.pk),
            "discipline": discipline.data["id"],
        },
        format="json",
    )
    assert course.status_code == 201, course.data
    version = CourseVersion.objects.get(course_id=course.data["id"])
    week = client.post(
        "/api/v1/weeks/",
        {"course_version": str(version.pk), "number": 1, "title": "Motion"},
        format="json",
    )
    assert week.status_code == 201, week.data
    topic = client.post(
        "/api/v1/topics/", {"week": week.data["id"], "title": "Velocity"}, format="json"
    )
    assert topic.status_code == 201, topic.data
    material = client.post(
        "/api/v1/materials/",
        {
            "topic": topic.data["id"],
            "title": "Notes",
            "type": "TEXT",
            "content": "Velocity is displacement per unit time.",
        },
        format="json",
    )
    assert material.status_code == 201, material.data
    assignment = client.post(
        "/api/v1/assignments/",
        {
            "topic": topic.data["id"],
            "title": "Calculate",
            "instructions": "10 meters in 2 seconds",
            "max_score": 20,
        },
        format="json",
    )
    assert assignment.status_code == 201, assignment.data
    scheme = client.post(
        "/api/v1/grading-schemes/",
        {"course_version": str(version.pk), "title": "Assessment"},
        format="json",
    )
    assert scheme.status_code == 201, scheme.data
    assert (
        client.post(
            "/api/v1/grading-components/",
            {"scheme": scheme.data["id"], "kind": "ASSIGNMENTS", "weight": 100},
            format="json",
        ).status_code
        == 201
    )
    response = client.post(
        f"/api/v1/courses/{course.data['id']}/publish/", {"version": str(version.pk)}, format="json"
    )
    assert response.status_code == 200, response.data
    response = client.post(
        f"/api/v1/groups/{group.data['id']}/assign/", {"course": course.data["id"]}, format="json"
    )
    assert response.status_code == 200, response.data
    learner = client_for(student)
    assert learner.get(f"/api/v1/courses/{course.data['id']}/tree/").status_code == 200
    assert learner.post(f"/api/v1/materials/{material.data['id']}/complete/").status_code == 200
    submitted = learner.post(
        f"/api/v1/assignments/{assignment.data['id']}/submit/",
        {
            "text_answer": "5 m/s",
            "files": SimpleUploadedFile(
                "answer.txt", b"5 meters per second", content_type="text/plain"
            ),
        },
    )
    assert submitted.status_code == 201, submitted.data
    assert (
        client.post(
            f"/api/v1/submissions/{submitted.data['id']}/grade/",
            {"score": 17, "comment": "Correct"},
            format="json",
        ).status_code
        == 200
    )
    enrollment = learner.get("/api/v1/enrollments/").data["results"][0]
    assert learner.get(f"/api/v1/enrollments/{enrollment['id']}/grades/").data["score"] == 85
    assert learner.get(f"/api/v1/enrollments/{enrollment['id']}/progress/").data["percent"] == 100


def test_deadline_enforced_and_empty_publish_rejected(world, client_for):
    from apps.courses.services import duplicate

    assignment = world["assignment"]
    assignment.deadline = timezone.now()
    assignment.save()
    assert (
        client_for(world["student"])
        .post(
            f"/api/v1/assignments/{assignment.pk}/submit/", {"text_answer": "late"}, format="json"
        )
        .status_code
        == 400
    )
    version = duplicate(world["version"], world["teacher"])
    material = version.weeks.first().topics.first().materials.first()
    material.type = "TEXT"
    material.content = ""
    material.save()
    assert (
        client_for(world["teacher"])
        .post(
            f"/api/v1/courses/{world['course'].pk}/publish/",
            {"version": str(version.pk)},
            format="json",
        )
        .status_code
        == 400
    )
