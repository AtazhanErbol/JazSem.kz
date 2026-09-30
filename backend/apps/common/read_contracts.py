"""Nested responses shared by schema generation and contract tests."""

from rest_framework import serializers

from apps.assignments.models import Assignment, SubmissionFile
from apps.courses.models import Course, CourseVersion, Topic, Week
from apps.grading.models import GradingComponent, GradingScheme
from apps.materials.models import Material
from apps.testing.models import AnswerOption, Question, Test, TestAttempt

from .serializers import serializer_for


class AttemptOptionOutput(serializers.Serializer):
    id = serializers.UUIDField()
    text = serializers.CharField()


class AttemptQuestionOutput(AttemptOptionOutput):
    type = serializers.ChoiceField(choices=Question._meta.get_field("type").choices)
    options = AttemptOptionOutput(many=True)


class AttemptDetailOutput(serializer_for(TestAttempt)):
    questions = AttemptQuestionOutput(many=True)
    answers = serializers.DictField(child=serializers.ListField(child=serializers.UUIDField()))
    server_time = serializers.DateTimeField()

    class Meta(serializer_for(TestAttempt).Meta):
        fields = [*serializer_for(TestAttempt).Meta.fields, "questions", "answers", "server_time"]
        read_only_fields = fields


class FileOutput(serializer_for(SubmissionFile)):
    file = serializers.BooleanField()


class MaterialOutput(serializer_for(Material)):
    file = serializers.BooleanField()


class AuthorQuestionOutput(serializer_for(Question)):
    options = serializer_for(AnswerOption)(many=True)

    class Meta(serializer_for(Question).Meta):
        fields = [*serializer_for(Question).Meta.fields, "options"]


class AuthorTestOutput(serializer_for(Test)):
    questions = AuthorQuestionOutput(many=True)

    class Meta(serializer_for(Test).Meta):
        fields = [*serializer_for(Test).Meta.fields, "questions"]


class StudentAssignmentOutput(serializer_for(Assignment)):
    class Meta(serializer_for(Assignment).Meta):
        exclude = ["source_chunks"]
        fields = None


class StudentTopicOutput(serializer_for(Topic)):
    materials = MaterialOutput(many=True)
    assignments = StudentAssignmentOutput(many=True)
    tests = serializer_for(Test)(many=True)

    class Meta(serializer_for(Topic).Meta):
        exclude = ["source_chunks"]
        fields = None


class AuthorTopicOutput(serializer_for(Topic)):
    materials = MaterialOutput(many=True)
    assignments = serializer_for(Assignment)(many=True)
    tests = AuthorTestOutput(many=True)


class StudentWeekOutput(serializer_for(Week)):
    topics = StudentTopicOutput(many=True)


class AuthorWeekOutput(serializer_for(Week)):
    topics = AuthorTopicOutput(many=True)


class StudentTreeOutput(serializers.Serializer):
    course = serializer_for(Course)()
    version = serializer_for(CourseVersion)()
    weeks = StudentWeekOutput(many=True)
    scheme = serializer_for(GradingScheme)(allow_null=True)
    components = serializer_for(GradingComponent)(many=True)


class AuthorTreeOutput(StudentTreeOutput):
    weeks = AuthorWeekOutput(many=True)


class ProgressOutput(serializers.Serializer):
    percent = serializers.FloatField()
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    completed_topics = serializers.ListField(child=serializers.UUIDField())
    read_topics = serializers.ListField(child=serializers.UUIDField())
    materials = serializers.ListField(child=serializers.UUIDField())
    assignments = serializers.ListField(child=serializers.UUIDField())
    tests = serializers.ListField(child=serializers.UUIDField())


class GradeComponentOutput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=GradingComponent._meta.get_field("kind").choices)
    weight = serializers.IntegerField()
    score = serializers.FloatField()


class GradesOutput(serializers.Serializer):
    score = serializers.FloatField()
    components = GradeComponentOutput(many=True)


class SavedOutput(serializers.Serializer):
    saved = serializers.BooleanField()


class MessageOutput(serializers.Serializer):
    message = serializers.CharField()


class CSRFOutput(serializers.Serializer):
    csrfToken = serializers.CharField()


class MailMetricsOutput(serializers.Serializer):
    counts = serializers.DictField(child=serializers.IntegerField())
    oldest_unsent_seconds = serializers.FloatField()
