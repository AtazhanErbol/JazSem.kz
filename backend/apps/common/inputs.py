from rest_framework import serializers


class Input(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) and not hasattr(data, "getlist"):
            raise serializers.ValidationError({"non_field_errors": ["Ожидается объект с полями."]})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Неизвестное поле." for key in unknown})
        return super().to_internal_value(data)


class Text(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class EmptyInput(Input):
    pass


class StudentInput(Input):
    student = serializers.UUIDField()


class CourseInput(Input):
    course = serializers.UUIDField()


class VersionInput(Input):
    version = serializers.UUIDField()


class SubmissionInput(Input):
    text_answer = Text(required=False, allow_blank=True, default="", max_length=100000)
    files = serializers.ListField(child=serializers.FileField(), required=False, max_length=5)


class ReviewInput(Input):
    comment = Text(required=False, allow_blank=True, default="", max_length=10000)


class RevisionInput(ReviewInput):
    comment = Text(max_length=10000)


class GradeInput(ReviewInput):
    score = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


class AnswerInput(Input):
    question = serializers.UUIDField()
    selected_options = serializers.ListField(child=serializers.UUIDField(), max_length=100)


def validated(request, serializer):
    data = serializer(data=request.data)
    data.is_valid(raise_exception=True)
    return data.validated_data


class DeleteDraftInput(VersionInput):
    confirmation = Text(max_length=300, trim_whitespace=False)


class GradingWeightsInput(VersionInput):
    weights = serializers.DictField(child=serializers.IntegerField(min_value=0, max_value=100))

    def validate_weights(self, value):
        if not value or set(value) - {"ASSIGNMENTS", "TESTS", "FINAL"}:
            raise serializers.ValidationError("Выберите допустимые виды работ.")
        if sum(value.values()) != 100:
            raise serializers.ValidationError("Сумма весов должна равняться 100%.")
        return value
