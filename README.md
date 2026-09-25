# JazSem.kz

Образовательная платформа для летнего семестра: Django REST API, React/TypeScript, PostgreSQL, Redis/Celery и приватное S3-хранилище. Интерфейс на русском и казахском языках.

Реализованы роли ADMIN/TEACHER/STUDENT, группы, дисциплины, версии курсов, назначения, учебный плеер, файлы, задания с доработкой, тесты с серверным таймером, оценки, прогресс, уведомления и AI-черновики с проверкой преподавателем. Все операции выполняются через backend; тестовый провайдер AI используется только в тестах.

**Статус:** реализация для интеграционной проверки. Успешные локальные тесты не заменяют приёмку production-инфраструктуры. Проверенные сценарии и оставшиеся release gates перечислены в [PROGRESS](docs/PROGRESS.md).

## Быстрый запуск через Docker

Требуются Docker Engine с Compose v2, свободные порты 5173/8000/9001. Команды выполняются из корня репозитория.

1. Скопируйте `.env.example` в `.env`.
2. Задайте собственные `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`, MinIO credentials и `DEV_SEED_PASSWORD` (не менее 12 символов). Пароли PostgreSQL/MinIO должны совпадать в соответствующих URL и S3-переменных.
3. Сгенерируйте `MAIL_ENCRYPTION_KEY`:

```sh
docker compose build backend
docker compose run --rm --no-deps backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

4. Запустите зависимости и примените миграции:

```sh
docker compose up -d postgres redis minio minio-init
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py seed_dev
docker compose up -d
```

Откройте [локальную платформу](http://localhost:5173). Development seed создаёт `admin@example.test`, `teacher@example.test`, `student@example.test`; пароль берётся только из `DEV_SEED_PASSWORD`. Повторный seed сохраняет существующие аккаунты и курсы. Он запрещён при `DEBUG=False` и не запускается автоматически.

AI по умолчанию выключен (`AI_ENABLED=false`). Для будущего включения подготовлен экономичный `gpt-5-nano` с лимитами ответа, повторов и суточного бюджета. Задайте `OPENAI_API_KEY`, актуальные цены, включите `AI_ENABLED` и перезапустите API/worker. [Модель и контроль расходов](docs/AI_COSTS.md).

## Разработка без Docker

Python 3.12, Node.js 22. SQLite используется только для быстрой локальной проверки; concurrency-проверки и production используют PostgreSQL.

```sh
python -m venv .venv
# Активируйте .venv подходящей командой для вашей ОС.
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
# Установите DEV_SEED_PASSWORD в environment.
python manage.py seed_dev
python manage.py runserver 127.0.0.1:8000
```

Во втором терминале:

```sh
cd frontend
npm ci
npm run dev
```

Django не загружает `.env` автоматически при запуске вне Compose: экспортируйте нужные переменные в окружение процесса. Без `REDIS_URL` development использует локальный cache; для фоновых задач запустите Redis, worker и beat. В development отсутствующий ключ шифрования выводится из development secret; production требует отдельный ключ. Console email допустим только локально и содержит письмо с временным паролем. В production используйте SMTP с TLS.

```sh
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

OCR требует Tesseract с `rus`, `kaz`, `eng` (установлены в backend Dockerfile). PDF сначала использует текстовый слой. DOCX не имеет стабильной пагинации: ссылки обозначают секцию документа; PPTX — слайд; PDF — страницу.

## Проверки

```sh
cd backend
ruff check .
ruff format --check .
pytest -q
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file ../docs/openapi.yml --validate
cd ../frontend
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
# При запущенных backend/frontend и заданном DEV_SEED_PASSWORD:
npm run e2e
```

Для backend-тестов на PostgreSQL установите `DATABASE_URL` на отдельную тестовую БД с правом создания test database. GitHub Actions использует PostgreSQL 16. E2E меняет development-данные: используйте отдельную локальную БД, не production.

## Документация

- [Архитектура](docs/ARCHITECTURE.md), [модель данных](docs/DATABASE.md), [решения](docs/DECISIONS.md)
- [API](docs/API.md), [OpenAPI](docs/openapi.yml), [AI pipeline](docs/AI_PIPELINE.md)
- [Безопасность](docs/SECURITY.md), [развёртывание](docs/DEPLOYMENT.md), [резервное копирование](docs/BACKUP.md)
- [Ход реализации и проверки](docs/PROGRESS.md)

В репозитории нет реальных контактов, юридических реквизитов, production-паролей или API keys. Публичные текстовые блоки настраиваются администратором в разделе «Контент».
