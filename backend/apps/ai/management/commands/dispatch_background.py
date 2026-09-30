from django.core.management.base import BaseCommand

from apps.ai.delivery import dispatch


class Command(BaseCommand):
    help = "Reconcile stale AI/extraction leases and dispatch durable pending records."

    def handle(self, *args, **options):
        dispatch()
        self.stdout.write("Dispatch pass completed; inspect source/job status for failures.")
