from django.conf import settings
from django.db import models

from apps.common.models import Entity


class Test(Entity):
    topic = models.ForeignKey("courses.Topic", on_delete=models.CASCADE, related_name="tests")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    max_score = models.PositiveIntegerField(default=100)
    time_limit_minutes = models.PositiveIntegerField(default=30)
    max_attempts = models.PositiveIntegerField(default=2)
    shuffle_questions = models.BooleanField(default=True)
    shuffle_answers = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    passing_score = models.PositiveIntegerField(default=50)
    status = models.CharField(max_length=20, default="DRAFT")
    is_required = models.BooleanField(default=True)
    is_final = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    time_limit_minutes__gt=0,
                    max_attempts__gt=0,
                    max_score__gt=0,
                    passing_score__lte=100,
                ),
                name="valid_test_limits",
            )
        ]


class Question(Entity):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    type = models.CharField(
        max_length=30, choices=[("SINGLE_CHOICE", "Single"), ("MULTIPLE_CHOICE", "Multiple")]
    )
    score = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    explanation = models.TextField(blank=True)
    source_chunks = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(score__gt=0), name="question_score_positive")
        ]


class AnswerOption(Entity):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TestAttempt(Entity):
    test = models.ForeignKey(Test, on_delete=models.PROTECT, related_name="attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    attempt_number = models.PositiveIntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, default="IN_PROGRESS")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    question_order = models.JSONField(default=list)
    option_order = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["test", "student", "attempt_number"], name="test_attempt_number"
            ),
            models.UniqueConstraint(
                fields=["test", "student"],
                condition=models.Q(status="IN_PROGRESS"),
                name="one_active_attempt",
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__gte=0, score__lte=100),
                name="test_score_range",
            ),
        ]


class TestAnswer(Entity):
    attempt = models.ForeignKey(TestAttempt, on_delete=models.PROTECT, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    selected_options = models.JSONField(default=list)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="attempt_answer")
        ]
