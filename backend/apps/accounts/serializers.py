from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.common.inputs import Input, Text
from apps.common.permissions import is_admin

from .models import User


class UserSerializer(serializers.ModelSerializer):
    owner_teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="TEACHER", is_active=True),
        allow_null=True,
        required=False,
    )
    owner_teacher_name = serializers.SerializerMethodField()

    def get_owner_teacher_name(self, obj) -> str:
        return (
            (obj.owner_teacher.get_full_name() or obj.owner_teacher.email)
            if obj.owner_teacher
            else ""
        )

    def validate(self, attrs):
        actor = self.context["request"].user
        role = attrs.get("role", self.instance.role if self.instance else "STUDENT")
        if self.instance and role != self.instance.role:
            raise serializers.ValidationError(
                {
                    "role": "Изменение роли существующего аккаунта запрещено: создайте отдельный аккаунт."
                }
            )
        if role != "STUDENT" and attrs.get("owner_teacher"):
            raise serializers.ValidationError(
                {"owner_teacher": "Преподавателя можно назначить только студенту."}
            )
        if not self.instance and role == "STUDENT":
            if is_admin(actor):
                if "owner_teacher" not in attrs:
                    raise serializers.ValidationError(
                        {
                            "owner_teacher": "Выберите преподавателя или явно оставьте студента нераспределённым."
                        }
                    )
            else:
                if attrs.get("owner_teacher", actor) != actor:
                    raise PermissionDenied("Нельзя назначить чужого преподавателя.")
                attrs["owner_teacher"] = actor
        return attrs

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "must_change_password",
            "preferred_language",
            "created_by",
            "owner_teacher",
            "owner_teacher_name",
            "created_at",
        ]
        read_only_fields = ["id", "username", "must_change_password", "created_by", "created_at"]


class LoginSerializer(Input):
    email = serializers.EmailField(max_length=254)
    password = Text(write_only=True, max_length=1024, trim_whitespace=False)


class ChangePasswordInput(Input):
    password = Text(write_only=True, max_length=1024, trim_whitespace=False)
    current_password = Text(write_only=True, max_length=1024, trim_whitespace=False)


class ResetPasswordInput(Input):
    password = Text(write_only=True, max_length=1024, trim_whitespace=False)
    uid = Text(max_length=100)
    token = Text(max_length=200, write_only=True)


class EmailSerializer(Input):
    email = serializers.EmailField(max_length=254)


class ProfileInput(Input):
    first_name = Text(max_length=150, allow_blank=True, required=False)
    last_name = Text(max_length=150, allow_blank=True, required=False)
    preferred_language = serializers.ChoiceField(
        choices=[("ru", "RU"), ("kk", "KZ")], required=False
    )
