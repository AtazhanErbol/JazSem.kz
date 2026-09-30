from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.api import ReadOnlyScoped, ScopedViewSet, representation
from apps.common.inputs import AnswerInput, EmptyInput, validated
from apps.common.serializers import serializer_for
from apps.testing.models import Test, TestAttempt
from apps.testing.services import finalize, save_answer, start


class TestDisplaySerializer(serializer_for(Test)):
    course_id = serializers.UUIDField(source="topic.week.course_version.course_id", read_only=True)
    course_version_id = serializers.UUIDField(source="topic.week.course_version_id", read_only=True)

    class Meta(serializer_for(Test).Meta):
        fields = [*serializer_for(Test).Meta.fields, "course_id", "course_version_id"]

    def validate(self, attrs):
        start = attrs.get("available_from", getattr(self.instance, "available_from", None))
        end = attrs.get("available_until", getattr(self.instance, "available_until", None))
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"available_until": "Окончание должно быть позже начала."}
            )
        for field in ["max_score", "time_limit_minutes", "max_attempts"]:
            if field in attrs and attrs[field] < 1:
                raise serializers.ValidationError({field: "Значение должно быть больше нуля."})
        if attrs.get("passing_score", 0) > 100:
            raise serializers.ValidationError({"passing_score": "Укажите процент от 0 до 100."})
        return attrs


class TestViewSet(ScopedViewSet):
    queryset = Test.objects.select_related("topic__week__course_version")
    serializer_class = TestDisplaySerializer

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        validated(request, EmptyInput)
        return Response(representation(start(self.get_object(), request.user), request))


class AttemptViewSet(ReadOnlyScoped):
    queryset = TestAttempt.objects.select_related("test", "student")
    serializer_class = serializer_for(TestAttempt)
    filterset_fields = ["test", "status"]

    def retrieve(self, request, *args, **kwargs):
        attempt = self.get_object()
        if attempt.status == "IN_PROGRESS" and attempt.expires_at <= timezone.now():
            attempt = finalize(attempt, attempt.student)
        data = representation(attempt, request)
        questions = {str(q.pk): q for q in attempt.test.questions.prefetch_related("options")}
        data["questions"] = []
        for qid in attempt.question_order:
            question = questions[qid]
            options = {str(o.pk): o for o in question.options.all()}
            data["questions"].append(
                {
                    "id": qid,
                    "text": question.text,
                    "type": question.type,
                    "options": [
                        {"id": oid, "text": options[oid].text} for oid in attempt.option_order[qid]
                    ],
                }
            )
        data["answers"] = {str(a.question_id): a.selected_options for a in attempt.answers.all()}
        data["server_time"] = timezone.now()
        return Response(data)

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        data = validated(request, AnswerInput)
        save_answer(
            self.get_object(),
            request.user,
            data["question"],
            [str(option) for option in data["selected_options"]],
        )
        return Response({"saved": True})

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        validated(request, EmptyInput)
        return Response(representation(finalize(self.get_object(), request.user), request))
