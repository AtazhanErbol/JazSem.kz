# JazSem: учебные материалы и ИИ-редактор

Ветка `feat/learning-materials-ai`, исходный main: `009864f`. Аудит и локальная проверка: 30 октября 2026. Production и реальные данные не изменялись. Merge и production deploy требуют подтверждения владельца.

## Аудит и архитектура

Лекция хранится в `courses.Topic.content`; отдельной Lecture нет. Существующий `materials.Material` — отдельная учебная активность с собственным прогрессом; записи и поведение сохранены. Изменена рабочая React-панель CourseBuilder/RecordForm, а не только Django Admin.

Опубликованные CourseVersion неизменяемы, Enrollment закрепляет студента за версией. Правки выполняются через существующее копирование в черновик. Общие editable/scope продолжают проверять права и блокировать версию/курс. Оценки, сдачи, ответы и активные попытки не переносятся на другую версию.

Существующие UploadTicket, signed S3 POST, quarantine, digest метаданных и private_response переиспользованы. Старые загрузки сохраняют прежнюю реализацию. Новый путь вложений проверяет диапазоны S3 и копирует объект внутри хранилища: большой файл не проксируется через Django/Vercel.

ИИ переиспользует AIJob/TaskDelivery/outbox, учёт расходов, provider configuration и запрет автоматического повтора неопределённого платного запроса. Новая операция LECTURE не требует отдельной очереди или миграции ИИ.

## Готовые функции

### Вложения и видео

Одна новая модель LearningAttachment с ровно одним FK к Topic, Assignment, Test или Question; общий API и React-компонент. Несколько файлов, drag & drop, выбор, прогресс/отмена, название, описание, размер, тип, дата загрузки, переименование, замена, сортировка между страницами, удаление с подтверждением, скачивание. В лекции — «Дополнительные материалы», в задании — «Материалы для выполнения», в тесте — «Материалы к тесту»; поддержаны файлы отдельных вопросов.

PDF/изображения имеют безопасный предпросмотр. DOC/DOCX, PPT/PPTX, XLS/XLSX, TXT/CSV, ODT/ODP/ODS доступны для скачивания. Backend проверяет имя, MIME, размер, сигнатуру/контейнер, ZIP-ограничения и настоящий OLE-каталог. Небезопасные имена, неподходящие контейнеры и макросы отклоняются.

MP4/WebM и несколько YouTube-видео поддержаны в задании, включая title/order/preview/replace/delete. Watch/youtu.be/Shorts/live/embed нормализуются в проверенный ID и фиксированный youtube-nocookie embed; произвольный iframe не принимается. Студент получает встроенный player и скачивание; истёкший URL можно обновить.

Прямая загрузка привязана к владельцу/объекту/method/digest/сроку/одноразовому ticket. HEAD и диапазоны привязаны к ETag; CopyObject использует CopySourceIfMatch. Подмена quarantine между проверкой и копированием отклоняется. Файлы приватны, JSON не содержит ключей хранилища, выдача использует временный signed URL. Вложения вопроса студент видит после начала попытки; правильные ответы/объяснения отсутствуют в публичных данных вопросов.

Вложения сохраняются после редактирования. При копировании курса клонируются связи/метаданные, а неизменяемый storage object переиспользуется. Замена создаёт новый ключ; удаление связи не удаляет файл старой версии. Orphan cleaner учитывает новую модель. Лекция только с файлами корректно учитывается в дереве и прогрессе.

### ИИ-лекции

В редакторе темы: создание, улучшение, расширение и перегенерация выбранного H2-раздела. Тема, дисциплина существующего курса, аудитория/сложность, ru/kk/en, цель/результаты, подробность и указания; опциональные обработанные источники того же курса.

Структурированный результат содержит цель, результаты, введение, термины, подробную теорию, примеры, типичные ошибки, выводы, самопроверку и источники. Проверка отклоняет слишком короткий полный ответ, опасную разметку и неизвестные ссылки. Источники выбираются из загруженных документов и серверного каталога известных официальных ресурсов; внешний поиск не имитируется.

AI draft сохраняется и доступен после перезагрузки, допускает ручное редактирование/сохранение. Применение требует подтверждения замены, после чего преподаватель сохраняет тему обычным способом. В открытом редакторе доступна отмена применения. expected_updated_at защищает сохранение от перезаписи правками другого окна (409). Никакого автоматического изменения опубликованной лекции.

Провайдер, модель и ключи остаются существующими. Отсутствие provider/worker вызывает честную диагностику. Неопределённый ответ/ошибка не запускают автоматический повтор платной генерации.

### Панель и чтение

Навигация администратора/преподавателя сгруппирована по обучению, проверке знаний, пользователям и ИИ, с фильтрацией по существующим разрешениям роли. Студенческие маршруты сохранены.

В длинных формах разделы, статусы, закреплённое сохранение, ошибки около полей, предупреждение об уходе, student preview. Новый объект можно сохранить черновиком и продолжить прикрепление файлов. Вопросы теста используют прежние формы без вложенных модальных окон.

Общий безопасный Markdown-reader: H2/H3, вложенные списки, таблицы со скроллом, код, KaTeX-формулы и читаемые интервалы. Сырой HTML, iframe и исполняемые URL не отображаются. Сохранены фирменные шрифты/красные акценты. Проверены RU/KK/EN-тексты и мобильная/настольная компоновка.

## Миграция

Единственная новая: `backend/apps/materials/migrations/0003_learningattachment.py`. Создаёт новую таблицу и ограничения «ровно один родитель»/kind. Существующие таблицы оценок, попыток, ответов, лекций и файлов не пересоздаются. Проверена на отдельной PostgreSQL; незаписанных миграций нет. Откат миграции после использования удалит новые вложения: перед таким откатом их нужно сохранить.

## Проверки

Все данные синтетические: отдельные PostgreSQL 16, Redis, MinIO и SMTP sink. Реальные API-ключи не использовались.

| Проверка | Результат |
| --- | --- |
| Полный backend pytest/PostgreSQL | 460 passed, 2 opt-in storage tests skipped |
| Отдельные реальные MinIO/S3 integration tests | 2 passed: signed POST, conditional copy, Range playback, приватность и запрет подмены |
| Frontend Vitest | 58 passed, 16 файлов |
| ESLint, TypeScript + Vite production build | passed |
| npm audit | 0 vulnerabilities; общая patched KaTeX для всех вложенных зависимостей |
| Ruff check / format | passed |
| Django check; makemigrations --check --dry-run | passed |
| OpenAPI validate --fail-on-warn | passed |
| pip check; pip-audit обоих lock-файлов | passed, известных уязвимостей не найдено |
| Полный Playwright | финальный прогон выполняется; результат обновится перед завершением PR |
| Gitleaks working sources | passed, no leaks |

Новый браузерный сценарий создаёт лекцию с несколькими файлами, редактирует/сохраняет/отменяет AI draft, загружает настоящий браузерный WebM, добавляет YouTube, создаёт тест с вложениями, публикует и проверяет просмотр/скачивание студентом без утечки ответов. Backend дополнительно проверяет роли/чужие файлы, старые версии/попытки, сохранность вложений, форматы/размер, прерывание/подмену, провайдерские ошибки и конфликт редактирования. В CI добавлен отдельный opt-in прогон на MinIO.

## Env и preview

Существующие обязательные env БД/хранилища/почты/авторизации/background сохраняются. Новые настройки имеют defaults:

| Переменная | Default | Назначение |
| --- | --- | --- |
| MAX_VIDEO_UPLOAD_MB | 250 | MiB; верхняя граница объекта 5 000 000 000 bytes |
| ATTACHMENT_UPLOAD_TICKET_SECONDS | 7200 | Финализация, максимум 86400; signed POST нужно начать в течение прежних 300 s |
| PRIVATE_MEDIA_URL_SECONDS | 900 | URL предпросмотра/видео; обычное скачивание сохраняет прежний короткий срок |
| AI_LECTURE_OUTPUT_TOKENS | 16000 | Выходной бюджет при включённых лимитах; unlimited Gemini по-прежнему не отправляет maxOutputTokens |
| PREVIEW_ISOLATED_RESOURCES | false | Preview only: true только после подключения отдельных ресурсов |

Используются существующие MAX_UPLOAD_MB, DIRECT_UPLOADS_ENABLED/VITE_DIRECT_UPLOADS (на Vercel уже включены), S3_BUCKET/ENDPOINT_URL/REGION/ACCESS_KEY/SECRET_KEY либо существующее отображение Tigris integration. Bucket приватный, с signed POST/GET и conditional CopyObject; CORS разрешает origin frontend. ИИ: существующие AI_ENABLED, AI_PROVIDER, provider key/model и queue variables. Модель Gemini не менялась. Секреты в Git не добавлены.

Vercel build вызывает storage setup и миграции. Поэтому feature preview останавливается **до этих операций**, пока PREVIEW_ISOLATED_RESOURCES не равен true. Не включайте флаг только ради успешной сборки: нужны отдельная PostgreSQL/ветка БД, отдельный bucket/ключ и отдельные очередь/background endpoints. Интеграции не должны наследовать production-ресурсы. После изоляции настройте preview env/CORS; существующий VERCEL_BRANCH_URL используется для frontend origin/CSRF/allowed hosts. Production этим заданием не изменяется.

После одобрения merge обычный forward-only build применит одну новую миграцию. Пересоздание БД или импорт данных не нужны; используйте существующий процесс backup перед выпуском.

## Ограничения

- MOV отклоняется с просьбой конвертировать в MP4/WebM. Нет transcoding и возобновляемого multipart-upload API. Codec должен поддерживаться браузером; иначе скачивание.
- Office/ODF скачиваются; сторонний публичный viewer не используется. Антивирус/модерация содержания файлов не добавлены.
- Живой платный вызов Gemini не выполнялся. Provider protocol и ошибки проверены fake transport, async workflow — изолированным synthetic provider. Конкретный учебный текст проверяет преподаватель.
- Undo применения ИИ доступен в открытом редакторе. Межсессионная история текстовых правок отдельно не создавалась; AI drafts и версии курса сохраняются.
- Каталог рекомендуемых источников ограничен известными ресурсами и выбранными файлами; автоматическая проверка внешних фактов/библиографии не заявляется.
- Google quotas и Vercel 300 s ceiling остаются внешними ограничениями. Нет гарантии неограниченного времени выполнения.
- S3-путь проверен на MinIO. Работающий Vercel preview и проверка именно Tigris требуют отдельных preview-ресурсов; production bucket не изменялся.

## Изменённые файлы

Полный список ниже и в Files changed PR. Runtime-артефакты, node_modules, ключи и локальные БД исключены из Git.

- `.env.example`
- `.github/workflows/ci.yml`
- `backend/apps/ai/contracts.py`
- `backend/apps/ai/gemini.py`
- `backend/apps/ai/lectures.py`
- `backend/apps/ai/prompts.py`
- `backend/apps/ai/provider.py`
- `backend/apps/ai/tasks.py`
- `backend/apps/ai/views.py`
- `backend/apps/common/api.py`
- `backend/apps/common/direct_uploads.py`
- `backend/apps/common/openapi.py`
- `backend/apps/common/read_contracts.py`
- `backend/apps/common/scope.py`
- `backend/apps/courses/services.py`
- `backend/apps/courses/views.py`
- `backend/apps/enrollments/read_models.py`
- `backend/apps/materials/attachments.py`
- `backend/apps/materials/management/commands/orphan_uploads.py`
- `backend/apps/materials/migrations/0003_learningattachment.py`
- `backend/apps/materials/models.py`
- `backend/apps/materials/remote_uploads.py`
- `backend/apps/materials/validation.py`
- `backend/apps/materials/youtube.py`
- `backend/apps/progress/services.py`
- `backend/config/settings/base.py`
- `backend/config/urls.py`
- `backend/config/vercel_build.py`
- `backend/config/vercel_environment.py`
- `backend/pyproject.toml`
- `backend/requirements-dev.txt`
- `backend/requirements.in`
- `backend/requirements.txt`
- `backend/tests/acceptance_provider.py`
- `backend/tests/lecture_fixture.py`
- `backend/tests/test_learning_attachments.py`
- `backend/tests/test_learning_storage_integration.py`
- `backend/tests/test_lecture_ai.py`
- `backend/tests/test_production_config.py`
- `backend/tests/test_vercel_environment.py`
- `docs/LEARNING_AUTHORING.md`
- `docs/openapi.yml`
- `frontend/e2e/admin-workspace.spec.ts`
- `frontend/e2e/authoring.spec.ts`
- `frontend/e2e/learning-materials.spec.ts`
- `frontend/e2e/manual-course.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/components/UI.tsx`
- `frontend/src/entities/types.ts`
- `frontend/src/features/ai/AIWizard.tsx`
- `frontend/src/features/authoring/Attachments.test.tsx`
- `frontend/src/features/authoring/Attachments.tsx`
- `frontend/src/features/authoring/LearningContent.test.tsx`
- `frontend/src/features/authoring/LearningContent.tsx`
- `frontend/src/features/authoring/LectureAssistant.tsx`
- `frontend/src/features/courses/CourseBuilder.tsx`
- `frontend/src/features/courses/CoursePlayer.tsx`
- `frontend/src/features/learning/AssignmentPage.tsx`
- `frontend/src/features/learning/TestPage.tsx`
- `frontend/src/features/manage/CreateLearning.test.tsx`
- `frontend/src/features/manage/RecordForm.tsx`
- `frontend/src/i18n/authoring.ts`
- `frontend/src/i18n/index.ts`
- `frontend/src/layouts/Shell.test.tsx`
- `frontend/src/layouts/Shell.tsx`
- `frontend/src/main.tsx`
- `frontend/src/services/directUpload.test.ts`
- `frontend/src/services/directUpload.ts`
- `frontend/src/styles/authoring.css`
