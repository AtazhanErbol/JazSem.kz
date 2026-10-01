"""Read-only data gate before additive RC constraints are applied."""

import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import F


class Command(BaseCommand):
    help = "Check known states and cross-table invariants without changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--legacy",
            action="store_true",
            help="Allow only the known pre-RC owner/mail columns to be deferred. Run again after additive migrations.",
        )

    def handle(self, **options):
        findings = {}
        deferred = []
        missing = []
        with connection.cursor() as cursor:
            columns = {
                table: {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, table)
                }
                for table in connection.introspection.table_names(cursor)
            }

        def available(label, field):
            model = apps.get_model(label)
            column = model._meta.get_field(field).column
            if column in columns.get(model._meta.db_table, set()):
                return True
            name = f"{label}.{field}"
            # A missing table is never an accepted legacy schema.
            if (
                options["legacy"]
                and model._meta.db_table in columns
                and name in {"accounts.User.owner_teacher", "notifications.MailOutbox.status"}
            ):
                deferred.append(name)
            else:
                missing.append(name)
            return False

        for label, field in [
            ("courses.Course", "status"),
            ("courses.CourseVersion", "status"),
            ("enrollments.Enrollment", "status"),
            ("assignments.Submission", "status"),
            ("testing.TestAttempt", "status"),
            ("ai.AIJob", "status"),
            ("ai.SourceDocument", "processing_status"),
            ("notifications.MailOutbox", "status"),
        ]:
            model = apps.get_model(label)
            if not available(label, field):
                continue
            allowed = [value for value, _ in model._meta.get_field(field).choices]
            findings[label + ".state"] = model.objects.exclude(**{field + "__in": allowed}).count()
        for label in ["enrollments.Enrollment", "enrollments.GroupCourseAssignment"]:
            model = apps.get_model(label)
            if all(
                [
                    available(label, "course"),
                    available(label, "course_version"),
                    available("courses.CourseVersion", "course"),
                ]
            ):
                findings[label + ".version_course"] = model.objects.exclude(
                    course_id=F("course_version__course_id")
                ).count()
        enrollment = apps.get_model("enrollments.Enrollment")
        if all(
            [
                available("accounts.User", "owner_teacher"),
                available("enrollments.Enrollment", "student"),
                available("enrollments.Enrollment", "course"),
                available("courses.Course", "teacher"),
            ]
        ):
            findings["enrollment.owner"] = enrollment.objects.exclude(
                student__owner_teacher_id=F("course__teacher_id")
            ).count()
        self.stdout.write(
            json.dumps(
                {
                    **findings,
                    "deferred": sorted(set(deferred)),
                    "missing_schema": sorted(set(missing)),
                },
                sort_keys=True,
            )
        )
        if missing:
            raise CommandError(
                "Preflight requires the listed schema. Use --legacy only before RC additive migrations."
            )
        if any(findings.values()):
            raise CommandError(
                "Preflight found invalid historical rows. Resolve explicitly; no records were changed."
            )
