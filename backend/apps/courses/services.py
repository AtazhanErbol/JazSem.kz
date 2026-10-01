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
    course = Course.objects.select_for_update().get(pk=version.course_id)
    version = CourseVersion.objects.select_for_update().get(pk=version.pk)
    editable(version, user)
    topics = [
        topic
        for week in version.weeks.prefetch_related(
            "topics__materials", "topics__assignments", "topics__tests"
        )
        for topic in week.topics.all()
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
            or any(m.is_required for m in t.materials.all())
            or any(a.is_required for a in t.assignments.all())
            or any(test.is_required for test in t.tests.all())
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
    from apps.testing.models import AnswerOption

    Course.objects.select_for_update().get(pk=version.course_id)
    version = CourseVersion.objects.select_for_update().get(pk=version.pk)
    target = new_version(version.course, user)

    def copy(obj, *, persist=True, **changes):
        fields = {
            f.attname: getattr(obj, f.attname)
            for f in obj._meta.fields
            if f.name not in ["id", "created_at", "updated_at"]
        }
        # Copy FK IDs without resolving each related object; overrides replace
        # the original foreign key, never pass both relation and *_id.
        for name, value in changes.items():
            field = obj._meta.get_field(name)
            fields[field.attname] = value.pk if field.is_relation else value
        copied = type(obj)(**fields)
        if persist:
            copied.save()
        return copied

    options = []
    for week in version.weeks.prefetch_related(
        "topics__materials", "topics__assignments", "topics__tests__questions__options"
    ):
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
                        options.append(copy(option, question=new_question, persist=False))
    # UUIDs are assigned on construction, and these plain models have no save
    # hooks. Keep all inserts inside the clone transaction and bound each batch.
    AnswerOption.objects.bulk_create(options, batch_size=500)
    scheme = GradingScheme.objects.filter(course_version=version).first()
    if scheme:
        new_scheme = copy(scheme, course_version=target)
        for component in scheme.components.all():
            copy(component, scheme=new_scheme)
    record(user, "course.duplicated", target, new={"source_version": str(version.pk)})
    return target
