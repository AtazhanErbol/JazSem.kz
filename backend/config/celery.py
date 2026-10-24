import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
app = Celery(
    "jazsem",
    **(
        {"task_cls": "config.vercel_strategy:VercelDjangoTask"}
        if os.environ.get("VERCEL") == "1"
        else {}
    ),
)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
