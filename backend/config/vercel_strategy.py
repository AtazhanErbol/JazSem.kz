"""Keep the complete solo-worker task lifecycle outside Vercel's async loop."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import wraps

from celery.contrib.django.task import DjangoTask
from celery.worker.strategy import default

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jazsem-celery")


class VercelDjangoTask(DjangoTask):
    Strategy = "config.vercel_strategy:sync_strategy"


def sync_strategy(task, app, consumer, **kwargs):
    handler = default(task, app, consumer, **kwargs)

    @wraps(handler)
    def handle(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # Ordinary Celery worker/ETA threads already provide a sync context.
            return handler(*args, **kwargs)
        # Vercel's sync queue callback runs inline in an async dispatcher. Move
        # the entire strategy, including Celery's prerun/postrun Django fixups,
        # to one sync thread. Waiting retains normal ACK/retry ordering and the
        # solo worker's serial execution. Context variables carry request OIDC.
        context = copy_context()

        def deliver():
            app.set_current()
            return handler(*args, **kwargs)

        return _executor.submit(context.run, deliver).result()

    return handle
