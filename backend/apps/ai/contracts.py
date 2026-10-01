from rest_framework import serializers

from apps.common.inputs import Input, Text

from .models import AICourseDraft, AIJob, AIUsageLog, DocumentChunk, SourceDocument


class SourceInput(Input):
    course = serializers.UUIDField()
    file = serializers.FileField()


class GenerationInput(Input):
    instruction = Text(max_length=2000, allow_blank=True, default="")
    page_from = serializers.IntegerField(min_value=1, required=False)
    page_to = serializers.IntegerField(min_value=1, required=False)
    mode = serializers.ChoiceField(choices=["NEW", "APPEND"], default="NEW")
    base_version = serializers.UUIDField(required=False)
    course = serializers.UUIDField()
    sources = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=30)
    weeks = serializers.IntegerField(min_value=1, max_value=16)
    language = serializers.ChoiceField(choices=[("ru", "RU"), ("kk", "KZ")])
    complexity = serializers.ChoiceField(
        choices=["basic", "intermediate", "advanced"], default="intermediate"
    )
    assignments = serializers.BooleanField(default=True)
    tests = serializers.BooleanField(default=True)

    def validate(self, data):
        if not data["instruction"]:
            data["instruction"] = (
                "Выдели ключевые темы и распределяй их последовательно по запрошенным новым неделям. "
                "Для каждой недели подготовь понятное объяснение с учебной целью. "
                "Если задания включены, предложи одно практическое задание с понятными требованиями к ответу. "
                "Если тесты включены, составь 5 вопросов с 5 вариантами, одним верным ответом и пояснением. "
                "Если исходного материала недостаточно, сделай меньше вопросов и укажи пробелы в source_gaps. "
                "Для изображений используй только распознанное содержимое, не угадывай нечитаемый текст. "
                "Все утверждения должны опираться на выбранные источники."
            )
        if ("page_from" in data) != ("page_to" in data):
            raise serializers.ValidationError("Укажите начало и конец диапазона страниц.")
        if data.get("page_from", 0) > data.get("page_to", 0):
            raise serializers.ValidationError("Начальная страница не может быть больше конечной.")
        if "page_from" in data and len(data["sources"]) != 1:
            raise serializers.ValidationError("Для диапазона страниц выберите ровно один PDF-файл.")
        if data["mode"] == "APPEND" and not data.get("base_version"):
            raise serializers.ValidationError(
                {"base_version": "Выберите версию курса для дополнения."}
            )
        if data["mode"] == "NEW":
            data.pop("base_version", None)
        if not data["assignments"] and not data["tests"]:
            raise serializers.ValidationError(
                {"assignments": "Для публикации курса добавьте задания или тесты."}
            )
        return data


class RegenerateInput(Input):
    week_index = serializers.IntegerField(min_value=0)
    topic_index = serializers.IntegerField(min_value=0)
    instruction = Text(max_length=2000)


class DraftInput(Input):
    data = serializers.DictField()


class SourceOutput(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    def get_file(self, obj) -> bool:
        return bool(obj.file)

    class Meta:
        model = SourceDocument
        fields = [
            "id",
            "course",
            "uploaded_by",
            "filename",
            "mime_type",
            "size",
            "file",
            "processing_status",
            "error",
            "excluded",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class JobOutput(serializers.ModelSerializer):
    estimated_cost = serializers.DecimalField(
        source="usage.estimated_cost", max_digits=12, decimal_places=6, read_only=True, default=None
    )
    parameters = serializers.SerializerMethodField()
    source_count = serializers.SerializerMethodField()

    def get_parameters(self, obj) -> dict:
        return {key: value for key, value in obj.parameters.items() if key != "draft_data"}

    def get_source_count(self, obj) -> int:
        return len({chunk["document"] for chunk in obj.source_snapshot})

    class Meta:
        model = AIJob
        fields = [
            "id",
            "course",
            "user",
            "type",
            "status",
            "progress",
            "current_step",
            "error",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "parameters",
            "source_count",
            "request_id",
            "estimated_cost",
        ]
        read_only_fields = fields


class DraftOutput(serializers.ModelSerializer):
    class Meta:
        model = AICourseDraft
        fields = ["id", "job", "data", "imported_version", "created_at", "updated_at"]
        read_only_fields = fields


class ChunkOutput(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ["id", "document", "page_number", "chunk_index", "content"]
        read_only_fields = fields


class UsageOutput(serializers.ModelSerializer):
    class Meta:
        model = AIUsageLog
        fields = [
            "id",
            "job",
            "user",
            "operation",
            "model",
            "input_tokens",
            "output_tokens",
            "estimated_cost",
            "duration",
            "status",
            "created_at",
        ]
        read_only_fields = fields
