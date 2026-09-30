from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.permissions import is_admin

from .models import User


@transaction.atomic
def lock_account_change(actor, account, changes):
    # Every activity mutation uses the same stable admin lock set, including inactive
    # admins. Filtering by is_active before locking would miss a concurrent change.
    admins = list(
        User.objects.select_for_update()
        .filter(Q(role="ADMIN") | Q(is_superuser=True))
        .order_by("pk")
    )
    if not User.objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied("Аккаунт заблокирован.")
    account = User.objects.select_for_update().get(pk=account.pk)
    if changes.get("is_active") is False:
        if account.pk == actor.pk:
            raise PermissionDenied("Нельзя заблокировать собственный аккаунт.")
        if is_admin(account) and not any(a.is_active and a.pk != account.pk for a in admins):
            raise ValidationError({"is_active": "Нельзя заблокировать последнего администратора."})
    if "owner_teacher" in changes:
        owner = changes["owner_teacher"]
        if getattr(owner, "pk", None) != account.owner_teacher_id:
            if not is_admin(actor):
                raise PermissionDenied("Только администратор меняет ответственного преподавателя.")
            from apps.academics.models import GroupMembership
            from apps.enrollments.models import Enrollment

            course_history = Enrollment.objects.filter(student=account)
            group_history = GroupMembership.objects.filter(student=account)
            if (
                course_history.exclude(course__teacher=owner).exists()
                or group_history.exclude(group__teacher=owner).exists()
            ):
                raise ValidationError(
                    {
                        "owner_teacher": "Смена преподавателя конфликтует с историей курсов или групп."
                    }
                )
    return account
