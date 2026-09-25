from rest_framework.permissions import BasePermission


class AccountReady(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and not request.user.must_change_password
        )


def is_admin(user):
    return user.is_superuser or user.role == "ADMIN"


def is_teacher(user):
    return is_admin(user) or user.role == "TEACHER"
