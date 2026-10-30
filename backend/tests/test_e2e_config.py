import os
import subprocess
import sys


def test_browser_worker_consumes_the_isolated_database_queue(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.celery import app; "
            "assert list(app.amqp.queues) == ['acceptance-jazsem_rc_queue']; "
            "q = app.amqp.queues['acceptance-jazsem_rc_queue']; "
            "assert q.exchange.name == 'acceptance-jazsem_rc_queue'; "
            "assert q.routing_key == 'acceptance-jazsem_rc_queue'",
        ],
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "config.settings.e2e",
            "E2E_ISOLATED": "1",
            "JAZSEM_RUNTIME_DIR": str(tmp_path),
            "DATABASE_URL": "postgresql://synthetic:synthetic@127.0.0.1/jazsem_rc_queue",
            "E2E_REDIS_URL": "redis://127.0.0.1:6379/0",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
