from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.api import ReadOnlyScoped, ScopedViewSet, representation
from apps.common.serializers import serializer_for
from apps.testing.models import Test, TestAttempt
from apps.testing.services import finalize, save_answer, start


class TestViewSet(ScopedViewSet):
    queryset = Test.objects.all()
    serializer_class = serializer_for(Test)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return Response(representation(start(self.get_object(), request.user), request))


class AttemptViewSet(ReadOnlyScoped):
    queryset = TestAttempt.objects.select_related("test", "student")
    serializer_class = serializer_for(TestAttempt)

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
        save_answer(
            self.get_object(),
            request.user,
            request.data.get("question"),
            request.data.get("selected_options", []),
        )
        return Response({"saved": True})

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        return Response(representation(finalize(self.get_object(), request.user), request))
