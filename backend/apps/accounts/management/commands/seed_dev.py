import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academics.models import Discipline, StudyGroup
from apps.accounts.models import User
from apps.assignments.models import Assignment
from apps.courses.models import Course, Topic, Week
from apps.courses.services import new_version, publish
from apps.enrollments.services import add_member, assign_group
from apps.grading.models import GradingComponent, GradingScheme
from apps.materials.models import Material
from apps.testing.models import AnswerOption, Question, Test


class Command(BaseCommand):
    help = "Create development-only accounts and a complete learning course."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_dev is disabled outside DEBUG development settings")
        password = os.environ.get("DEV_SEED_PASSWORD")
        if not password:
            raise CommandError("Set DEV_SEED_PASSWORD (at least 12 characters)")
        if len(password) < 12:
            raise CommandError("Password must contain at least 12 characters")
        users = {}
        for role, first, last in [
            ("ADMIN", "Администратор", "JazSem"),
            ("TEACHER", "Айдана", "Серикова"),
            ("STUDENT", "Алихан", "Омаров"),
        ]:
            user, created = User.objects.get_or_create(
                username=role.lower(),
                defaults={
                    "email": f"{role.lower()}@example.test",
                    "role": role,
                    "first_name": first,
                    "last_name": last,
                    "must_change_password": False,
                    "created_by": users.get("TEACHER"),
                },
            )
            if created:
                user.set_password(password)
                user.save()
            users[role] = user
        if Course.objects.exists():
            self.stdout.write("Accounts exist; existing courses preserved.")
            return
        discipline = Discipline.objects.create(
            name="Прикладная математика", code="MATH-01", created_by=users["ADMIN"]
        )
        discipline.teachers.add(users["TEACHER"])
        course = Course.objects.create(
            title="Прикладная математика · Летний семестр",
            description="От базовых уравнений к решению практических задач.",
            discipline=discipline,
            teacher=users["TEACHER"],
        )
        version = new_version(course, users["TEACHER"])
        for i, title in enumerate(["Линейные уравнения", "Системы уравнений"], 1):
            week = Week.objects.create(course_version=version, number=i, order=i, title=title)
            topic = Topic.objects.create(week=week, title=title)
            Material.objects.create(
                topic=topic,
                title="Конспект: " + title,
                content="Линейное уравнение имеет вид ax + b = 0. При a ≠ 0 его решение: x = −b/a. Например, 2x + 4 = 0, следовательно x = −2. Подставьте ответ в исходное уравнение, чтобы проверить решение.",
            )
            Assignment.objects.create(
                topic=topic,
                title="Практическая работа " + str(i),
                instructions="Решите уравнение 3x − 9 = 0. Объясните каждый шаг и выполните проверку.",
            )
            test = Test.objects.create(topic=topic, title="Проверка знаний " + str(i))
            question = Question.objects.create(
                test=test, text="Каково решение уравнения 2x + 4 = 0?", type="SINGLE_CHOICE"
            )
            for text in ["−2", "2", "0"]:
                AnswerOption.objects.create(question=question, text=text, is_correct=text == "−2")
        scheme = GradingScheme.objects.create(course_version=version)
        GradingComponent.objects.create(scheme=scheme, kind="ASSIGNMENTS", weight=60)
        GradingComponent.objects.create(scheme=scheme, kind="TESTS", weight=40)
        publish(version, users["TEACHER"])
        course.refresh_from_db()
        group = StudyGroup.objects.create(name="Магистратура · Лето", teacher=users["TEACHER"])
        add_member(users["TEACHER"], group, users["STUDENT"])
        assign_group(users["TEACHER"], group, course)
        self.stdout.write(
            self.style.SUCCESS(
                "Created dev accounts: admin/teacher/student@example.test. Password is DEV_SEED_PASSWORD."
            )
        )
