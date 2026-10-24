import asyncio
import threading
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from celery import Celery, signals
from celery.concurrency.solo import TaskPool
from celery.worker.state import task_ready
from django.db import close_old_connections

from apps.accounts.models import User
from config.vercel_strategy import VercelDjangoTask


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("async_dispatch", [False, True])
def test_real_strategy_and_trace_keep_orm_and_task_signals_in_sync_context(async_dispatch):
    owner = User.objects.create_user(username="thread-probe")
    request_context = ContextVar("synthetic_oidc")
    request_context.set("request-context")
    phases = []
    caller_thread = threading.get_ident()

    def check(phase):
        # Real ORM queries catch Django's async guard in the task AND signals.
        assert User.objects.filter(pk=owner.pk).exists()
        assert request_context.get() == "request-context"
        phases.append((phase, threading.get_ident()))

    app = Celery("strategy-probe", broker="memory://", backend="cache+memory://")

    @app.task(base=VercelDjangoTask, name="strategy_probe", ignore_result=True)
    def probe():
        check("task")

    task = probe._get_current_object()

    def prerun(**kwargs):
        close_old_connections()
        check("prerun")

    def postrun(**kwargs):
        check("postrun")
        close_old_connections()

    signals.task_prerun.connect(prerun, sender=task, weak=False)
    signals.task_postrun.connect(postrun, sender=task, weak=False)
    requests = []
    pool = TaskPool()

    def execute(request):
        requests.append(request)
        request.execute_using_pool(pool)

    consumer = SimpleNamespace(
        hostname="strategy-probe",
        connection_errors=(ConnectionError,),
        event_dispatcher=None,
        timer=Mock(),
        apply_eta_task=Mock(),
        disable_rate_limits=True,
        task_buckets={},
        on_task_request=execute,
        _limit_task=Mock(),
        _limit_post_eta=Mock(),
        pool=pool,
        controller=SimpleNamespace(state=SimpleNamespace(revoked=set())),
    )
    handler = task.start_strategy(app, consumer)
    body = {"args": [], "kwargs": {}}
    message = Mock(
        payload=body,
        headers={"task": task.name, "id": str(uuid4())},
        delivery_info={},
        properties={},
        content_type="application/json",
        content_encoding="utf-8",
    )
    ack, reject = Mock(), Mock()

    async def dispatch():
        handler(message, body, ack, reject, [])

    try:
        if async_dispatch:
            asyncio.run(dispatch())
        else:
            handler(message, body, ack, reject, [])
        assert [phase for phase, _ in phases] == ["prerun", "task", "postrun"]
        threads = {thread for _, thread in phases}
        assert len(threads) == 1
        assert (caller_thread in threads) is (not async_dispatch)
        ack.assert_called_once()
        reject.assert_not_called()
    finally:
        signals.task_prerun.disconnect(prerun, sender=task)
        signals.task_postrun.disconnect(postrun, sender=task)
        for request in requests:
            task_ready(request)
        app.close()
