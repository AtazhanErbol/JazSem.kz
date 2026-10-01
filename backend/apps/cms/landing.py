"""Validated, localized landing drafts and published snapshots."""

import json

from django.db import transaction
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record, selected_fields
from apps.common.permissions import AdminReady

from .models import ContentBlock

PREFIX = "__landing_"
TEXT_KEYS = "heroLabel heroTitle heroAccent heroText heroCta features how forTeachers forStudents login continue aboutTitle aboutText feature1 feature1Text feature2 feature2Text feature3 feature3Text howTitle how1 how1Text how2 how2Text how3 how3Text teacherTitle teacherText studentTitle studentText aiFlow faq faq1 faq1Answer faq2 faq2Answer faq3 faq3Answer finalTitle copyright sceneLabel sceneTag sceneTitle sceneText sceneHint imageAlt".split()
TEXT_KEYS += "featuresTitle learningLabel learningTitle learningText learningNote weekExample weekTitle week1 week1Text week2 week2Text week3 week3Text creationLabel creationTitle creationText manualTitle manualText manualImport assistedTitle assistedText assistedReview creationNote".split()
SECTIONS = ["about", "features", "learning", "creation", "how", "teachers", "faq", "final"]


class LandingInput(serializers.Serializer):
    language = serializers.ChoiceField(choices=["ru", "kk"])
    texts = serializers.DictField(
        child=serializers.CharField(max_length=4000, allow_blank=True), default=dict
    )
    hidden = serializers.ListField(
        child=serializers.ChoiceField(choices=SECTIONS), max_length=len(SECTIONS), default=list
    )
    image = serializers.URLField(max_length=2000, allow_blank=True, default="")
    publish = serializers.BooleanField(default=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({"non_field_errors": ["Expected an object."]})
        if set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["Unknown fields."]})
        return super().to_internal_value(data)

    def validate_texts(self, value):
        if set(value) - set(TEXT_KEYS):
            raise serializers.ValidationError("Unknown text fields.")
        return value

    def validate_image(self, value):
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("Use an HTTPS image URL.")
        return value


class LandingView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LandingInput

    def get(self, request):
        language = request.query_params.get("language", "ru")
        if language not in ["ru", "kk"]:
            raise serializers.ValidationError({"language": "Use ru or kk."})
        draft = request.query_params.get("draft") == "1"
        if draft and not AdminReady().has_permission(request, self):
            raise PermissionDenied()
        keys = [PREFIX + "draft", PREFIX + "live"] if draft else [PREFIX + "live"]
        for key in keys:
            block = ContentBlock.objects.filter(key=key, language=language).first()
            if block:
                return Response(json.loads(block.body))
        return Response({"texts": {}, "hidden": [], "image": ""})

    @transaction.atomic
    def post(self, request):
        if not AdminReady().has_permission(request, self):
            raise PermissionDenied()
        serializer = LandingInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        language = data.pop("language")
        publish = data.pop("publish")
        for key in ["draft", "live"] if publish else ["draft"]:
            block, _ = ContentBlock.objects.update_or_create(
                key=PREFIX + key,
                language=language,
                defaults={
                    "title": "Landing " + key,
                    "body": json.dumps(data, ensure_ascii=False),
                    "is_published": False,
                },
            )
            record(
                request.user,
                "landing." + ("publish" if key == "live" else "save"),
                block,
                new=selected_fields(block),
            )
        return Response(data)
