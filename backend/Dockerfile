FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-kaz tesseract-ocr-eng libpcre2-8-0 libssl3t64 openssl openssl-provider-legacy && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 app
COPY --chown=app:app . .
RUN mkdir -p /app/private-media /app/staticfiles && chown -R app:app /app
USER app
EXPOSE 8000
FROM base AS development
USER root
RUN pip install --no-cache-dir -r requirements-dev.txt
USER app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
FROM base AS production
USER root
# Installers are build/development tools, not part of the immutable runtime.
RUN python -m pip uninstall -y pip setuptools wheel
USER app
ENV DJANGO_SETTINGS_MODULE=config.settings.production
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-", "--access-logformat", "%(h)s %(m)s %(U)s %(s)s %(L)s"]
