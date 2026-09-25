from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
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
            "created_at",
        ]
        read_only_fields = ["id", "username", "must_change_password", "created_by", "created_at"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    current_password = serializers.CharField(write_only=True, required=False)
    uid = serializers.CharField(required=False)
    token = serializers.CharField(required=False)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
