# Текущее состояние JazSem.kz

Финальный код `ac8ad868cdc6c2bf0067f7e731b5d5f581d2f96c`: 145 backend, 8 frontend, 21 browser, полный production-profile fault/restore прогон и сопоставимые замеры выполнены 01.10.2026. Остались только явно перечисленные внешние условия выпуска и решение по остаточным native CVE.

Единственный актуальный статус, матрица 13 направлений, SHA, команды и доказательства: [RELEASE_CANDIDATE](RELEASE_CANDIDATE.md).

Исторические записи 25–30 сентября сохранены в [history](history/PROGRESS_BEFORE_FINAL_VERIFICATION.md). Старые числа тестов, enum warnings, A1–A4 и PostgreSQL deadlock оттуда не являются текущими открытыми дефектами.

Локальная приёмка использует только отдельные jazsem_rc_* PostgreSQL, приватный синтетический S3, настоящий Redis/Celery, fake SDK provider и SMTP sink. Пользовательские данные, платный AI и внешняя рассылка не используются. Production release не одобрен. Новые workflow ещё не запускались на GitHub: публикация ветки/PR требует отдельного разрешения.
