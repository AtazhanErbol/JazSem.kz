"""Read-only data gate before additive RC constraints are applied."""

import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F


class Command(BaseCommand):
    help = "Check known states and cross-table invariants without changing data."

    def handle(self, **options):
        findings = {}
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
            allowed = [value for value, _ in model._meta.get_field(field).choices]
            findings[label + ".state"] = model.objects.exclude(**{field + "__in": allowed}).count()
        for label in ["enrollments.Enrollment", "enrollments.GroupCourseAssignment"]:
            model = apps.get_model(label)
            findings[label + ".version_course"] = model.objects.exclude(
                course_id=F("course_version__course_id")
            ).count()
        enrollment = apps.get_model("enrollments.Enrollment")
        findings["enrollment.owner"] = enrollment.objects.exclude(
            student__owner_teacher_id=F("course__teacher_id")
        ).count()
        self.stdout.write(json.dumps(findings, sort_keys=True))
        if any(findings.values()):
            raise CommandError(
                "Preflight found invalid historical rows. Resolve explicitly; no records were changed."
            )
