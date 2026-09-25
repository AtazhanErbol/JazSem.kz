import secrets
import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.common.permissions import is_admin, is_teacher
from apps.notifications.services import queue_mail

from .models import User
from .serializers import EmailSerializer, LoginSerializer, PasswordSerializer, UserSerializer


@method_decorator(csrf_protect, name="dispatch")
class AuthView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    serializer_class = LoginSerializer

    def get_throttles(self):
        self.throttle_scope = "csrf" if self.request.method == "GET" else "auth"
        return super().get_throttles()

    def get(self, request):
        return Response({"csrfToken": get_token(request)})

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account = User.objects.filter(email__iexact=data.validated_data["email"]).first()
        user = authenticate(
            request,
            username=account.username if account else "__missing__",
            password=data.validated_data["password"],
        )
        if not user:
            raise ValidationError({"email": "Неверный email или пароль."})
        login(request, user)
        return Response(UserSerializer(user).data)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        data = {
            key: request.data[key]
            for key in ["first_name", "last_name", "preferred_language"]
            if key in request.data
        }
        serializer = UserSerializer(request.user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmailSerializer

    def post(self, request):
        logout(request)
        return Response(status=204)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PasswordSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data.get("current_password", "")):
            raise ValidationError({"current_password": "Неверный текущий пароль."})
        validate_password(serializer.validated_data["password"], request.user)
        request.user.set_password(serializer.validated_data["password"])
        request.user.must_change_password = False
        request.user.save()
        update_session_auth_hash(request, request.user)
        return Response(UserSerializer(request.user).data)


@method_decorator(csrf_protect, name="dispatch")
class ForgotView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "reset"
    serializer_class = EmailSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user:
            url = f"{settings.FRONTEND_URL}/reset-password?uid={urlsafe_base64_encode(force_bytes(user.pk))}&token={default_token_generator.make_token(user)}"
            queue_mail(
                user,
                "JazSem.kz",
                (
                    "Құпиясөзді қалпына келтіру: "
                    if user.preferred_language == "kk"
                    else "Восстановить пароль: "
                )
                + url,
            )
        return Response({"message": "Если аккаунт существует, письмо будет отправлено."})


@method_decorator(csrf_protect, name="dispatch")
class ResetView(ForgotView):
    serializer_class = PasswordSerializer

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            uid = urlsafe_base64_decode(data.get("uid", "")).decode()
            user = User.objects.select_for_update().get(pk=uid, is_active=True)
        except (ValueError, UnicodeDecodeError, User.DoesNotExist):
            raise ValidationError("Ссылка недействительна.")
        if not default_token_generator.check_token(user, data.get("token", "")):
            raise ValidationError("Ссылка недействительна.")
        validate_password(data["password"], user)
        user.set_password(data["password"])
        user.must_change_password = False
        user.save()
        return Response({"message": "Пароль изменён."})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.none()
    serializer_class = UserSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    search_fields = ["email", "first_name", "last_name", "username"]
    filterset_fields = ["role", "is_active"]
    ordering_fields = ["created_at", "last_name", "email"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        user = self.request.user
        if is_admin(user):
            return User.objects.all().order_by("-created_at")
        if user.role == "TEACHER":
            return User.objects.filter(created_by=user, role="STUDENT").order_by("-created_at")
        return User.objects.filter(pk=user.pk)

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get("role", "STUDENT")
        if not is_teacher(user) or (not is_admin(user) and role != "STUDENT"):
            raise PermissionDenied()
        password = secrets.token_urlsafe(18)
        account = serializer.save(
            username=f"u_{uuid.uuid4().hex[:20]}", created_by=user, must_change_password=True
        )
        account.set_password(password)
        account.save()
        message = (
            f"{settings.FRONTEND_URL}/login\nEmail: {account.email}\n"
            + ("Уақытша құпиясөз: " if account.preferred_language == "kk" else "Временный пароль: ")
            + password
        )
        queue_mail(account, "JazSem.kz — аккаунт", message)
        record(user, "account.created", account, new={"role": role})

    @transaction.atomic
    def perform_update(self, serializer):
        if not is_teacher(self.request.user):
            raise PermissionDenied()
        if (
            "role" in serializer.validated_data
            and serializer.validated_data["role"] != serializer.instance.role
        ):
            raise ValidationError(
                {
                    "role": "Изменение роли существующего аккаунта запрещено: создайте отдельный аккаунт."
                }
            )
        old = {"is_active": serializer.instance.is_active}
        obj = serializer.save()
        record(self.request.user, "account.updated", obj, old, {"is_active": obj.is_active})

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        if not is_teacher(request.user) or obj.pk == request.user.pk:
            raise PermissionDenied()
        obj.is_active = False
        obj.save()
        record(request.user, "account.blocked", obj)
        return Response(status=status.HTTP_204_NO_CONTENT)
