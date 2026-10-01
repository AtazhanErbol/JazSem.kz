# JazSem.kz — итоговая проверка release candidate, 01.10.2026

**Доступные локальные инженерные проверки пройдены. Production release не одобрен: внешние условия и принятие остаточного риска перечислены ниже.** Платных AI-вызовов, внешних писем и публикации не было.

## 1. Версия и границы доказательств

- Ветка: `release/rc-hardening`.
- Исходная версия: `a712f644bcd7185bd9d99943ce499d0cb6943654`.
- Код приложения, тестов, CI и контейнеров на момент полной RC-приёмки: **`ac8ad868cdc6c2bf0067f7e731b5d5f581d2f96c`**. Backend, frontend и полный production-profile прогон выполнены на этой версии; браузерный отчёт подтверждает чистое дерево.
- Документирующий коммит `a127359` не менял исполняемый код. После него внесены UI-изменения, перечисленные в дополнении ниже; текущий frontend уже не идентичен полной RC-приёмке.
- Новые GitHub Actions **не запускались**. Исторический [CI 36696183172](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36696183172) на исходном SHA подтверждал 125 PostgreSQL/7 frontend тестов, development services и сборку images. Он не заменяет новые локальные E2E/runtime/fault/restore результаты.
- Локальные коммиты: `7c88e72` — backend/read models/recovery; `2f2df14` — рабочие места и браузерные сценарии; `ba52efe` — воспроизводимая приёмка/CI/runbooks; `b596ec9` — PostgreSQL OpenAPI и AI controls; `538f9e6` — локализация восстановления AI; `ac8ad86` — корректная постановка storage fault после принятого upload.

Все базы `jazsem_rc_*`, аккаунты `example.test`, storage и почта синтетические. Рабочая пользовательская база не мигрировалась, не очищалась и не восстанавливалась из тестового дампа. Force-push/rebase/merge/tag/deployment не выполнялись; push/PR требуют отдельного разрешения.

## Дополнение: завершение интерфейса после RC-приёмки

01.10.2026, актуальный код `27ca055` в `release/rc-hardening`:

- `bce4405`: раздельные стили поиска/фильтров/пагинации, выравнивание доставки писем и адаптивные отступы.
- `b7dcfd4`: оформление создания курса/дисциплины, назначения студентам/группам, загрузки файла; объяснение весов, итогового балла и обязательных элементов прогресса на RU/KK.
- `27ca055`: после успешной загрузки источника очищается также native file input; добавлены регрессии средних баллов/взвешенного вклада, прогресса, пустого курса и казахских пояснений.

На `27ca055` прошли **12 frontend unit-тестов (5 файлов), ESLint, TypeScript и production build**. Браузерная проверка UI на `b7dcfd4`: формы создания курса и дисциплины, grading/sharing, группа, AI upload, оценки и прогресс; пять изменённых экранов на мобильном КЗ, без горизонтального переполнения. На `bce4405` проверены 18 основных страниц на широком RU и мобильном KK. Скриншоты хранятся локально в ignored `.runtime/`; это ручная проверка, не новый полный E2E-прогон. Финальный reset input подтверждён чтением кода/сборкой, успешная отправка файла в браузере после него отдельно не воспроизводилась.

Backend, schema, container definitions и правила расчёта/прохождения не менялись. **145 backend и 21 browser, fault/restore и performance evidence ниже относятся к `ac8ad86`**, не являются повторным полным прогоном на новом frontend. Полный CI на обновлённой ветке предстоит после отдельного разрешения на push/PR. Production-приёмка и внешние условия раздела 7 остаются открытыми.

## 2. Матрица всех 13 направлений

`verified` означает подтверждение уже существующего поведения; `fixed and verified` — реализованное исправление и проверку. Статусы относятся к указанной локальной среде и сценариям, а не к универсальной гарантии отсутствия дефектов.

| № | Направление | Статус | Что подтверждено / доказательство |
|---|---|---|---|
| 1 | Владение студентами | verified | Явный owner/отсутствие owner, created_by, чужой преподаватель, назначение/группы и сохранение истории: `test_release_access`, `test_permissions`, lifecycle E2E, restore |
| 2 | Доступ и валидация | fixed and verified | Scoped lists/actions/FK/downloads, скрытые ответы, frozen published versions, структурированные 4xx/503, last-admin; `test_contracts`, `test_permissions`, `test_runtime_security`, concurrency, OpenAPI |
| 3 | Фоновые операции | fixed and verified | Настоящие SIGKILL/Redis/storage/SMTP; stable delivery, fencing, bounded recovery, cancellation, UNCERTAIN usage/reservation; `runtime-faults.json`, recovery/concurrency tests |
| 4 | Администратор | fixed and verified | Создание/редактирование преподавателя, дисциплина, студент/владелец, группы/курс, results; mail/operations только ADMIN; `lifecycle`, `admin-workspace`, role API tests |
| 5 | Преподаватель | fixed and verified | Ручной course/version/week/topic/material/assignment/test, checklist, grading, publish/assign/revision, новый draft сохраняет старые enrollments; `authoring`, `lifecycle`, clone/history regressions |
| 6 | Продолжение обучения | fixed and verified | Допустимая сохранённая тема/активность, fallback, refresh/logout/login, ответы и серверное истечение попытки; `learning`, `audit`, `lifecycle`; completion не подменяется проходным баллом |
| 7 | Поиск/фильтры/URL | fixed and verified | Серверные allowlists/count/sort/page, refresh/Back/Forward, RemoteSelect и выбранная запись за первой страницей; `test_workspace_filters`, `url-state` |
| 8 | Формы и обратная связь | fixed and verified | RU/KK field/ARIA errors, сохранение текста/файла, dirty guards, двойной submit, pending/Escape/Cancel/focus, 400/403/409/429/503; `forms`, `management`, AI integration, unit `useAction` |
| 9 | Производительность | fixed and verified | Сопоставимые PG25/100 и browser before/after, summaries вместо fan-out, bulk clone, route splitting, targeted invalidation; query/byte budgets и сырые наблюдения |
| 10 | AI/история/расходы | fixed and verified | Реальный HTTP → DB outbox → Redis → worker → fake SDK → review/edit/reload/regenerate/import/publish; retry/exclude/citations, pagination, idempotence, late/cancel/uncertain budget; живое качество — внешний gate |
| 11 | Mobile RU/KK/a11y | fixed and verified | 390/768/1280, ADMIN/TEACHER/STUDENT/AI, формы/таблицы/диалоги/player, keyboard/focus, длинный текст, қазақша, 200% text reflow; не полный WCAG-аудит и не сертификация browser zoom |
| 12 | Очистка | fixed and verified | Удалены неиспользуемый AI_MAX_RETRIES/старые дублирующие Activities; runtime/dev dependencies разделены; настоящий S3 dry-run/manifest/apply сохраняет общие и новые ссылки/sentinel |
| 13 | Финальная verification | fixed and verified | 145 backend + 8 frontend + 21 browser, preflight/migrations/schema, production runtime/TLS/proxy/fault/restore/scans, безопасные artifacts и согласованные runbooks; target release gates отдельно blocked |

Машинные отчёты и ограничения: [measurements/README](measurements/README.md), [test-summary](measurements/test-summary.json), [browser-suite](measurements/browser-suite.json), [evidence-index](measurements/evidence-index.json).

## 3. Подтверждённые исправления и снятые гипотезы

Подтверждены и исправлены: 500 при отказе Redis в throttled endpoint → fail-closed 503/Retry-After; неверная классификация SMTP 451 recipient/550 DATA → bounded retry/operator action; отсутствие UNCERTAIN usage после смерти за provider boundary → единственная запись с сохранённым резервом; пропущенный audit в переопределённых course/material actions → allowlisted metadata; preflight на пустой/legacy schema → структурированная ошибка/контролируемое deferred поле; повторный Escape в dialog; технические AI complexity/RECOVERING keys. Добавлены целевые regressions, затем выполнены полные suites.

Также закрыты неполный URL state, ненужные tree question reads, results fan-out, row-by-row clone options, глобальная invalidation после локальных мутаций, потеря контекста Continue, неразличимые dashboard loading/error/empty и ошибки форм без локализованной ARIA-связи. Изменения измерены или покрыты браузерной/API-регрессией. Оценивание, обязательные assessed activities и привязка старых enrollments к версиям сохранены.

Не объявлены новыми дефектами: ранее исправленные A1–A4 и PostgreSQL deadlock. Несовпадение OpenAPI integer/int64 было воспроизводимой разницей генерации SQLite/PostgreSQL; checked-in схема теперь проверяется на PostgreSQL. Storage fault harness раньше сам выключал short worker до HTTP admission и получал ожидаемый 503: исправлен сценарий (пауза heavy после доступного admission), защита приложения не ослаблена. После reconnect допускаются только четыре попытки явного pre-admission `background_unavailable`, не повтор неизвестного результата или AI-вызова; финальный upload принят на четвёртой попытке, durable source затем пережил storage outage.

Первый финальный локальный pytest встретил Windows Temp PermissionError (33 pass/112 setup errors); повтор с новой project-local `--basetemp` дал 145/0/0. Ошибка кодировки одноразового сравнения OpenAPI исправлена явным UTF-8. Эти сбои среды не скрыты и не являются успешной продуктовой проверкой; успешным считается полный повтор. Одна non-failing pytest cache permission warning осталась и не повлияла на assertions.

## 4. Финальный прогон и воспроизведение

Среда: Windows 11, i5-11400H (6 cores/12 logical), Python 3.12.14, Node 24.21.0, PostgreSQL 16.15/Redis 7.4.11 в WSL Ubuntu 26.04, Docker 29.1.3/Compose 2.40.3, Chromium 153.0.8010.12. Новый CI задаёт Node 22; его удалённый запуск остаётся not run до разрешённого push.

| Проверка | Результат |
|---|---|
| Полный PostgreSQL pytest | **145 passed, 0 failed, 0 errors, 0 skipped**, 37.42 s; в том числе 8 concurrency |
| Frontend Vitest | **8 passed, 0 failed, 0 skipped**, 4 files, 2.21 s |
| Playwright | **21 passed, 0 failed, 0 skipped, 0 flaky**, 238.47 s; чистое дерево `ac8ad86` |
| Ruff/format | Passed, 179 backend files; два изменённых fault scripts также checked/formatted |
| ESLint / TypeScript / production build | Passed |
| Fresh PostgreSQL migration / drift / system / pip check | Passed, нет новых миграций/расхождения models |
| OpenAPI | `--validate --fail-on-warn` passed, PostgreSQL результат совпадает с `docs/openapi.yml` |
| Production-profile pipeline | Полный последовательный прогон init/TLS/HTTP/infrastructure/fault/restore/extras/proxy/scans, exit 0 |
| Python/npm audit | runtime 70 packages / dev 104 packages, 0 known findings; npm 0 |
| Secret scan | Вся история на кодовом SHA: 27 commits, 0 findings; working source 0, redaction 100%; evidence-коммит проверяется отдельно |

Локальный Python — `../venv/Scripts/python.exe` от корня репозитория, `../../venv/Scripts/python.exe` от backend/frontend. Ниже `python` означает этот интерпретатор. Переменные окружения передаются процессам; секреты не печатать. `DATABASE_URL` должен указывать на отдельную loopback PostgreSQL базу `jazsem_rc_*`, не на пользовательскую `.env`.

```sh
# backend/, DJANGO_SETTINGS_MODULE=config.settings.test
python -m ruff check .
python -m ruff format --check .
python manage.py migrate --noinput
python manage.py makemigrations --check --dry-run
python manage.py check
python -m pip check
python manage.py spectacular --validate --fail-on-warn --file ../.runtime/final/openapi-ac8.yml
# Compare both UTF-8 files to docs/openapi.yml, then:
python -m pytest -q --tb=short --basetemp=../.runtime/final/pytest-ac8-complete --junitxml=../.runtime/final/backend-ac8.xml
# Use a NEW basetemp and synthetic DB for a fresh rerun.
python -m pip_audit -r requirements.txt --no-deps --disable-pip --format=json --output=../.runtime/final/pip-runtime-ac8.json
python -m pip_audit -r requirements-dev.txt --no-deps --disable-pip --format=json --output=../.runtime/final/pip-development-ac8.json

# frontend/
npm run lint
npm run typecheck
npm test
npm run build
npm audit --json

# repository root; fresh synthetic DB, loopback E2E_REDIS_URL,
# DEV_SEED_PASSWORD, E2E_BACKEND_PORT=8011, E2E_FRONTEND_PORT=5190,
# E2E_SMTP_PORT=1027, E2E_MAIL_PORT=8027 set in environment:
python scripts/run_browser_acceptance.py
```

Production-profile воспроизводится в Linux из tracked source archive проверенного SHA, без `.env`. Настоящие production settings; локальный CA/STARTTLS sink; non-root/read-only/cap-drop/no-new-privileges. Fake-provider overlay подключается только после обычного smoke и заменяет только сетевую границу SDK. Команды ниже также находятся в `.github/workflows/ci.yml`:

```sh
export RC_SOURCE_REF=ac8ad868cdc6c2bf0067f7e731b5d5f581d2f96c
python scripts/acceptance_prepare.py
# In this Windows/WSL run, certificates were generated by the Windows
# venv and copied into the fresh WSL lab because host WSL has no venv.
docker compose -f infra/compose.acceptance.yml build
docker compose -f infra/compose.acceptance.yml up -d postgres redis minio mail
docker compose -f infra/compose.acceptance.yml run --rm backend python manage.py migrate --noinput
python scripts/acceptance_phase.py init
docker compose -f infra/compose.acceptance.yml up -d backend short heavy beat web edge
python scripts/acceptance_phase.py tls
python scripts/acceptance_phase.py http
python scripts/acceptance_infrastructure.py
mkdir -p .runtime/acceptance/control
sudo chown 10001:10001 .runtime/acceptance/control
docker compose -f infra/compose.acceptance.yml -f infra/compose.acceptance-ai.yml up -d
python scripts/acceptance_faults.py
python scripts/acceptance_restore.py
python scripts/acceptance_extras.py
python scripts/acceptance_proxy.py
python scripts/scan_acceptance_images.py
# Against actual repository history, not a Git-less source archive:
python scripts/scan_secrets.py
```

Финальный свежий lab: `/tmp/jazsem-rc-complete-ac8ad86`. Safe reports скопированы в `.runtime/final/production-ac8/`; JUnit — `.runtime/final/backend-ac8.xml`, браузер — `.runtime/browser-b22fd8f4/safe-artifacts/`. Экспортированные отчёты находятся в [measurements](measurements/README.md). Только фиксированный synthetic Compose project `jazsem-acceptance` допускает reset после сохранения evidence; не применять cleanup к другим проектам/базам.

Фактические runtime результаты: три используемых Redis TLS клиента, два отказа untrusted CA и hostname mismatch; `/health` остаётся 200, `/ready` становится 503 при остановке S3/Redis/short/heavy и возвращается 200 после восстановления; два реальных proxy clients подтверждают spoof rejection и независимый throttle. SIGKILL до boundary даёт один результат после восстановления, после boundary — FAILED/UNCERTAIN без replay; cancel/timeout/duplicate не создают второго draft. Storage outage даёт 0 partial chunks, retry сохраняет immutable chunk IDs; corrupt PDF завершает FAILED, oversized upload — 400.

OCR: настоящий PNG 14.4 MP под 1 CPU/1536 MiB, контролируемый timeout за 60.80 s; почта и expiry в short очереди выполняются за 0.59 s во время heavy processing. Restore: **43 модели, 9 объектов**, backup 5.79 s, restore+verify 5.12 s; это quiesced synthetic rehearsal, не production SLA. Защищённый download проверен Django session HTTP client, сетевой HTTPS — отдельным smoke. SMTP 451 → SENT после 2 attempts, 550/decryption → FAILED после 1; at-least-once SMTP не гарантирует отсутствие дубликата при uncertain accept.

## 5. Производительность и budgets

Обе версии измерены последовательно на одном host/PostgreSQL 16.15/Python и одинаковых синтетических данных: 33 темы, 257 вопросов, 1 026 вариантов, 25 и 100 enrollments; видимая страница — 25 строк. Проверены 174 исходных backend-файла baseline против Git; менялся только параметр размера benchmark. Семь warm samples, p50 — медиана, nearest-rank p95 — максимум семи наблюдений. Это лабораторное сравнение, не production capacity/tail latency. Standalone PostgreSQL в WSL не имел отдельного CPU/memory cap; во время пары не выполнялись OCR, сборки или другие benchmarks.

| Операция, dataset 25 | SQL до → после | p50 ms до → после | p95 ms до → после | Bytes до → после |
|---|---:|---:|---:|---:|
| Student tree | 12 → 10 | 96.89 → 33.03 | 178.83 → 77.43 | 121233 → 121233 |
| Editor tree | 11 → 11 | 425.99 → 105.29 | 473.83 → 157.78 | 431899 → 431899 |
| Publish | 59 → 27 | 88.50 → 62.75 | 157.72 → 119.71 | service call, no HTTP payload |
| Duplicate | 1803 → 391 | 1410.23 → 455.92 | 1427.12 → 494.77 | service call, no HTTP payload |
| Оба results режима, старые endpoints | 375 → 400 | 807.04 → 1156.68 | 876.32 → 1208.47 | 5950 → 5950 |
| Новый summaries endpoint | — → 11 | — → 51.31 | — → 57.51 | — → 20689 |

Старый benchmark делает **50 HTTP** для progress+grades 25 студентов; один прежний UI-экран выбирал один режим и делал **25** result-data requests. Теперь видимая страница запрашивает **1** scoped summaries response с именами, progress и grades, поэтому payload-контракт расширился: сравнивать bytes как идентичные ответы неверно. Старые endpoints не удалены и в искусственном fan-out benchmark стали медленнее; UI больше не вызывает их по каждой строке. При **100 enrollments** summaries остаётся 1 HTTP/11 SQL, 20755 bytes, p50/p95 **51.54/54.30 ms**. Старый combined fan-out baseline 801.92/881.61 ms; duplicate 1465.41/1966.25 → 449.78/500.37 ms. Все raw observations: `postgres-*.json`.

Browser: один measurement script, одинаковый public CMS dataset/API, production preview, Chromium 153.0.8010.12, 1440×900, CPU slowdown 4×, 40 ms/5 Mbit/s down/1 Mbit/s up, семь cold contexts на route. Builds исходного `a712f64` и итогового `ac8ad86` выполнены с одинаковым lockfile. Внутри каждой выборки были два настоящих клика RU/KK; сохранены Event Timing и long tasks.

| Метрика | До | После |
|---|---:|---:|
| Landing JS raw / gzip bytes | 619512 / 188667 | **485651 / 153761** |
| Landing LCP p50 / p95 ms | 1356 / 1888 | **1276 / 1308** |
| Login JS raw / gzip bytes | 619512 / 188667 | 611839 / 193186 |
| Login LCP p50 / p95 ms | 848 / 860 | 1052 / 1072 |
| Total build JS raw / gzip bytes | 619512 / 188667 | 714448 / 231373 |
| Landing / login resource requests | 14 / 12 | 13 / 16 |
| Landing / login maximum observed Event Timing ms | 224 / 56 | 192 / 72 |
| Landing / login maximum observed long task ms | 340 / 130 | 332 / 119 |

**Не все показатели улучшились.** Landing запрашивает на 21.6% меньше raw JS и на 18.5% меньше gzip. Login стал примерно на 204 ms медленнее по медиане и добавил четыре resource requests: отдельный auth chunk добавляет загрузочные зависимости; gzip login +2.4%, total build raw +15.3% вследствие новых возможностей/границ chunks. Эти регрессии сохранены в evidence, без заявления об ускорении каждого экрана. Они укладываются в зафиксированные byte budgets; жёсткого latency SLA не введено. CLS landing остался около 0.0000213, login 0.00660 → 0. Event Timing имеет threshold 16 ms, число event records не равно числу кликов; это не field INP. Полные `browser-before-comparable.json` / `browser-after.json` содержат traces/request paths/samples.

CI regression budgets: summaries ≤13 SQL при 25/100 enrollments; clone 102 options ≤50 queries; student tree не читает question/options tables; result-data HTTP/page не растёт с числом строк. Landing ≤525000 raw/170000 gzip, login ≤650000 raw/210000 gzip, total build JS ≤800000 raw. Миллисекундные пороги на общей CI-машине не используются. Backend/API assertions, frontend E2E и byte budgets прошли на финальном коде.

Reproduction: из каждого isolated source checkout выполнить `MEASURE_SHA=<sha> MEASURE_ENROLLMENTS=25|100 MEASURE_OUT=<json> python -m pytest tests/benchmark_course.py -q` с той же отдельной PostgreSQL и новой project-local `--basetemp`; старому benchmark применить только параметр enrollments. Затем последовательно собрать/запустить оба frontend production preview и вызвать финальный `frontend/e2e/measure.mjs` с `MEASURE_URL`/`MEASURE_OUT`. Baseline намеренно превышает новый landing budget; JSON сохраняется до budget exception. Локальные paired harnesses и четыре raw outputs сохранены в `.runtime/final/`.


## 6. Миграции и сохранность данных

Новых миграций нет, исторические migrations не изменены. Совпадение models/schema проверено; пустая, legacy и текущая схемы покрыты preflight regressions. Ownership/created_by, старые enrollment.course_version, submissions/attempts/grades/progress, drafts/citations/usage, ciphertext и общие storage keys сохраняются; restore проверяет эти связи.

Единый порядок описан в [DEPLOYMENT](DEPLOYMENT.md): check/config + schema-compatible preflight → backup → maintenance/остановка writers и старых workers + quiesced snapshot → только недостающие additive migrations legacy-схемы → полный preflight → остальные forward migrations → preflight/check → sentinel → matching API/short/heavy/beat/web → readiness/smoke → отдельное разрешение на трафик. Для текущей a712-схемы — обычный forward migrate; старые migration targets не запускать назад. Пустая БД сначала явно подтверждается как новая, затем migrate/full preflight.

Откат только на schema-compatible application digest с остановкой несовместимых workers. Reverse schema/автоматическое переназначение owners/удаление истории не разрешены. Restore существующих данных сначала в отдельную среду. [BACKUP](BACKUP.md), [BACKGROUND_RECOVERY](BACKGROUND_RECOVERY.md), [MAIL_RECOVERY](MAIL_RECOVERY.md), [OPERATIONS](OPERATIONS.md), [STATES_AND_LOCKS](STATES_AND_LOCKS.md), README/PROGRESS согласованы с этим порядком; прежнее ошибочное обещание SDK retry убрано из AI_PIPELINE.

## 7. Security scan и внешние release gates

Frontend image: 0 Trivy findings. Backend native image: **76 HIGH, 1 CRITICAL**, плюс 96 MEDIUM/133 LOW/3 UNKNOWN. Это не «чистый образ». Для точных текущих HIGH/CRITICAL package/version/CVE нет Debian fixed version; bounded reachability review и compensating controls описаны в [SECURITY_REVIEW](SECURITY_REVIEW.md). CI не скрывает findings и отвергает новые/непроверенные/исправимые HIGH/CRITICAL, изменившуюся версию или истёкший review (15.10.2026). Exploit path приложения в выполненных проверках не воспроизведён; это не доказательство безопасности всех native parsers. До реальных документов необходимы принятие остаточного риска владельцем/security review либо обновление/замена затронутых компонентов с повторной приёмкой.

Synthetic PostgreSQL/Redis/MinIO images также имеют findings, включая исправимые; они не рекомендуются и не одобрены как production services. Production Compose их не разворачивает: нужны поддерживаемые PostgreSQL/Redis/private S3. Их версии/IAM/TLS проверяются на целевой инфраструктуре. Все findings и image IDs сохранены в [image-scans](measurements/image-scans.json), без blanket ignore.

| Внешнее условие | Статус | Минимальное действие владельца |
|---|---|---|
| GitHub Actions на новой версии | not run | Отдельно разрешить push/PR; после публикации проверить новые browser/runtime/secret jobs |
| Целевой staging/production | blocked | Предоставить разрешённую среду, DNS/TLS/proxy chain, секреты через secret manager, поддерживаемые PG/Redis/private S3; выполнить runbook/smoke там |
| Остаточные native CVE | blocked | Security/owner review точных findings, принять документированный риск или обновить безопасный runtime и повторить gates |
| Gmail/Workspace inbox | not run | Сохранить SMTP credentials локально/в secret manager и разрешить конкретное тестовое письмо; проверить TLS, доставку и reset flow в настоящем inbox |
| Живой AI RU/KK/citations | not run | Отдельно согласовать модель, актуальную цену, малую выборку и бюджет; затем проверить качество с преподавателем |
| OCR/языковая/предметная редактура | not run | Дать разрешённые реальные документы и редактора; synthetic timeout test не проверяет распознавание |
| Контакты/юридические тексты | blocked | Предоставить реальные утверждённые сведения; фиктивные реквизиты не добавлялись |
| Monitoring/backup policy | blocked | Настроить адресатов alerts, retention/access/encryption, независимое хранение ключей и restore на целевой среде |

## 8. Решение

**RC engineering gates пройдены в описанной локальной среде.** Нет незавершённого доступного инженерного пункта, замаскированного под внешний блокер. Остаточные риски и ограничения измерений сохранены. **Production release: not approved** до внешней приёмки и отдельного решения владельца. Публикация ветки и PR в рамках этой задачи не выполнялись.
