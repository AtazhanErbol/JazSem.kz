from rest_framework import serializers

from apps.common.permissions import is_teacher

_serializers = {}


class ScopedSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("request").user if self.context.get("request") else None
        if user and not is_teacher(user):
            for key in ["is_correct", "explanation", "source_chunks"]:
                data.pop(key, None)
        if "file" in data:
            data["file"] = bool(instance.file)
        data.pop("extracted_text", None)
        return data


def serializer_for(model, readonly=()):
    key = (model, tuple(readonly))
    if key in _serializers:
        return _serializers[key]
    result = type(
        model.__name__ + "Serializer",
        (ScopedSerializer,),
        {
            "Meta": type(
                "Meta",
                (),
                {
                    "model": model,
                    "fields": "__all__",
                    "read_only_fields": ["id", "created_at", "updated_at", *readonly],
                },
            )
        },
    )
    _serializers[key] = result
    return result
