# Установка и запуск JazSem.kz

Эта инструкция запускает весь проект локально: React, Django, PostgreSQL, Redis, MinIO и фоновые задачи Celery. Команды ниже подходят для PowerShell на Windows. Для публичного сервера используйте [production-инструкцию](DEPLOYMENT.md).

## 1. Подготовка

Установите Git и Docker Desktop с Compose v2, запустите Docker Desktop и дождитесь состояния Engine running. Свободными должны быть порты 5173, 8000 и 9001. Если порт 8000 занят другим проектом, укажите `BACKEND_PORT=8001` в `.env`: API будет доступен на 8001, а сайт останется на 5173. Связь сайта с backend внутри Docker сохраняется. При первом запуске Docker скачивает образы и устанавливает OCR/библиотеки; это может занять несколько минут, особенно при медленном интернете.

```powershell
git clone https://github.com/AtazhanErbol/JazSem.kz.git
cd JazSem.kz
```

Если проект уже скачан и работает, используйте его существующую папку и `.env`. Обновление исходников не требует создания новой базы или повторного заполнения демонстрационных данных.

## 2. Локальные настройки

Для новой установки следующая команда создаёт `.env` со случайными паролями, согласованными настройками PostgreSQL/MinIO и ключом шифрования писем. Python на компьютере не нужен:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.12-slim python scripts/init_local_env.py
```

При наличии Python 3.12 можно выполнить `python scripts/init_local_env.py` вместо Docker-команды. Скрипт сохраняет существующий `.env` и не выводит пароли. Откройте созданный файл в редакторе: значение `DEV_SEED_PASSWORD` понадобится для первого входа. `.env` исключён из Git; сохраняйте его отдельно в защищённом месте.

По умолчанию включены development-настройки, письма выводятся в локальный журнал, AI выключен. Ручное создание курсов, заданий и тестов не требует AI или SMTP.

## 3. Первый запуск

Выполняйте команды по очереди, дожидаясь успешного завершения каждой:

```powershell
docker compose build
docker compose up -d postgres redis minio minio-init
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py seed_dev
docker compose up -d
docker compose ps
```

`minio-init` должен завершиться с кодом 0; остальные сервисы должны работать. `seed_dev` создаёт демонстрационный курс и три аккаунта только в development. В существующей базе он не меняет пароли имеющихся аккаунтов и не заменяет курсы.

| Что открыть | Адрес |
| --- | --- |
| Сайт и вход | http://localhost:5173 |
| Состояние API | http://localhost:8000/health/ |
| Готовность зависимостей | http://localhost:8000/ready/ |
| Документация API | http://localhost:8000/api/docs/ |
| Консоль локального хранилища | http://localhost:9001 |

Главная страница сайта находится на **5173**. Пустой путь на **8000** возвращает 404: этот порт обслуживает API.

Первый вход: `admin@example.test`, `teacher@example.test` или `student@example.test`; пароль — значение `DEV_SEED_PASSWORD` в вашем `.env`. Для существующих пользователей используйте их текущие данные входа. Администратор создаёт реальные аккаунты в разделе «Пользователи», вручную или через Excel.

## 4. Письма и AI

Чтобы отправлять приглашения, восстановление пароля и уведомления через Gmail, задайте в `.env`:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-account@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=your-account@gmail.com
```

Укажите свой адрес и пароль приложения Google, созданный в настройках аккаунта с двухэтапной проверкой. Обычный пароль аккаунта сюда не подходит. `MAIL_ENCRYPTION_KEY` должен оставаться прежним, иначе сохранённые письма не удастся расшифровать. У пользователя должен быть реальный адрес; `example.test` письма не принимает. Отправку выполняют Celery и beat, статусы видны в «Доставка писем».

Для AI добавьте собственный `OPENAI_API_KEY`, установите `AI_ENABLED=true` и проверьте модель/лимиты в [инструкции по расходам](AI_COSTS.md). API оплачивается отдельно; без ключа и API-баланса генерация недоступна. OCR через Tesseract работает локально. Все секреты вводятся только в `.env`.

После изменения `.env` пересоздайте процессы, чтобы они получили новые значения:

```powershell
docker compose up -d --force-recreate backend celery heavy beat
```

## 5. Повторный запуск, остановка и обновление

После первоначальной установки запускайте весь проект:

```powershell
docker compose up -d
```

Также можно нажать Start у группы `jazsem` в Docker Desktop. Для остановки используйте `docker compose stop`. Курсы, пользователи и файлы сохраняются в Docker volumes. Не удаляйте volumes и не используйте `down -v`, если хотите сохранить данные.

После получения новой версии кода и резервного копирования данных:

```powershell
git pull --ff-only
docker compose build
docker compose stop backend celery heavy beat frontend
docker compose run --rm backend python manage.py migrate
docker compose up -d
```

Резервная копия исходников в GitHub не содержит базу, файлы пользователей и `.env`. Для переноса установленных данных следуйте [инструкции резервного копирования](BACKUP.md).

## 6. Если что-то не работает

```powershell
docker compose ps -a
docker compose logs --tail=80 backend frontend
docker compose logs --tail=80 celery heavy beat
docker compose exec -T backend python manage.py check
```

При `Failed to fetch` проверьте работу backend и открывайте сайт с `localhost:5173`, как указано в `.env`. Если письма остаются в очереди — проверьте Celery/beat; при ошибке SMTP — локальные параметры отправителя. Не публикуйте журналы с письмами, временными паролями или другими секретами.

Для внешнего доступа требуются отдельные production-настройки, HTTPS, домен, резервное копирование и проверка внешних сервисов. Локальный Compose предназначен для разработки и проверки.
