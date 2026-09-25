from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.common.scope import editable
from apps.grading.models import GradingComponent, GradingScheme

from .models import Course, CourseVersion


@transaction.atomic
def new_version(course, user):
    course = Course.objects.select_for_update().get(pk=course.pk)
    number = (course.versions.aggregate(n=Max("version_number"))["n"] or 0) + 1
    return CourseVersion.objects.create(course=course, version_number=number, created_by=user)


@transaction.atomic
def publish(version, user):
    version = CourseVersion.objects.select_for_update().get(pk=version.pk)
    editable(version, user)
    course = Course.objects.select_for_update().get(pk=version.course_id)
    topics = [
        topic for week in version.weeks.prefetch_related("topics") for topic in week.topics.all()
    ]
    if not topics or any(not t.title.strip() for t in topics):
        raise ValidationError("Курс должен содержать темы.")
    if any(
        not t.content.strip()
        and not t.materials.exists()
        and not t.assignments.exists()
        and not t.tests.exists()
        for t in topics
    ):
        raise ValidationError("Каждая тема должна содержать учебный материал или активность.")
    components = list(GradingComponent.objects.filter(scheme__course_version=version))
    if sum(c.weight for c in components) != 100:
        raise ValidationError("Сумма весов оценивания должна равняться 100%.")
    from apps.assignments.models import Assignment
    from apps.testing.models import Test

    assignments = Assignment.objects.filter(topic__week__course_version=version)
    tests = Test.objects.filter(topic__week__course_version=version).prefetch_related(
        "questions__options"
    )
    for component in components:
        available = (
            assignments.exists()
            if component.kind == "ASSIGNMENTS"
            else tests.filter(is_final=component.kind == "FINAL").exists()
        )
        if not available:
            raise ValidationError(f"Нет активностей для компонента {component.kind}.")
    for test in tests:
        if (
            test.available_from
            and test.available_until
            and test.available_until <= test.available_from
        ):
            raise ValidationError("Некорректные даты теста.")
        if not test.questions.exists():
            raise ValidationError("Тест должен содержать вопросы.")
        for question in test.questions.all():
            options = list(question.options.all())
            count = sum(o.is_correct for o in options)
            if len(options) < 2 or not count or (question.type == "SINGLE_CHOICE" and count != 1):
                raise ValidationError("Проверьте варианты и правильные ответы теста.")
    for topic in topics:
        for material in topic.materials.all():
            if material.type == "TEXT" and not material.content.strip():
                raise ValidationError("Текстовый материал не должен быть пустым.")
            if material.type == "VIDEO_LINK" and not material.external_url.startswith("https://"):
                raise ValidationError("Добавьте HTTPS ссылку на видео.")
            if material.type not in ["TEXT", "VIDEO_LINK"] and not material.file:
                raise ValidationError("Добавьте файл материала.")
    if not any(
        t.is_required
        and (
            t.content.strip()
            or t.materials.filter(is_required=True).exists()
            or t.assignments.filter(is_required=True).exists()
            or t.tests.filter(is_required=True).exists()
        )
        for t in topics
    ):
        raise ValidationError("Добавьте хотя бы один обязательный элемент обучения.")
    assignments.update(status="PUBLISHED")
    tests.update(status="PUBLISHED")
    version.status = "PUBLISHED"
    version.published_at = timezone.now()
    version.save()
    course.current_version = version
    course.status = "PUBLISHED"
    course.save()
    record(user, "course.published", course, new={"version": str(version.pk)})
    return version


@transaction.atomic
def duplicate(version, user):
    target = new_version(version.course, user)

    def copy(obj, **changes):
        fields = {
            f.name: getattr(obj, f.name)
            for f in obj._meta.fields
            if f.name not in ["id", "created_at", "updated_at"]
        }
        fields.update(changes)
        return type(obj).objects.create(**fields)

    for week in version.weeks.all():
        new_week = copy(week, course_version=target)
        for topic in week.topics.all():
            new_topic = copy(topic, week=new_week)
            for material in topic.materials.all():
                copy(material, topic=new_topic)
            for assignment in topic.assignments.all():
                copy(assignment, topic=new_topic, status="DRAFT")
            for test in topic.tests.all():
                new_test = copy(test, topic=new_topic, status="DRAFT")
                for question in test.questions.all():
                    new_question = copy(question, test=new_test)
                    for option in question.options.all():
                        copy(option, question=new_question)
    scheme = GradingScheme.objects.filter(course_version=version).first()
    if scheme:
        new_scheme = copy(scheme, course_version=target)
        for component in scheme.components.all():
            copy(component, scheme=new_scheme)
    return target
