from rest_framework import serializers

from apps.common.inputs import Input, Text

from .models import AICourseDraft, AIJob, AIUsageLog, DocumentChunk, SourceDocument


class SourceInput(Input):
    course = serializers.UUIDField()
    file = serializers.FileField()


class GenerationInput(Input):
    course = serializers.UUIDField()
    sources = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=30)
    weeks = serializers.IntegerField(min_value=1, max_value=16)
    language = serializers.ChoiceField(choices=["ru", "kk"])
    complexity = serializers.ChoiceField(
        choices=["basic", "intermediate", "advanced"], default="intermediate"
    )
    assignments = serializers.BooleanField(default=True)
    tests = serializers.BooleanField(default=True)

    def validate(self, data):
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
