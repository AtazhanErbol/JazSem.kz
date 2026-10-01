# Текущее состояние JazSem.kz

Единственный актуальный статус, матрица 13 направлений, SHA, команды и доказательства: [RELEASE_CANDIDATE](RELEASE_CANDIDATE.md).

Исторические записи 25–30 сентября сохранены в [history](history/PROGRESS_BEFORE_FINAL_VERIFICATION.md). Старые числа тестов, enum warnings, A1–A4 и PostgreSQL deadlock оттуда не являются текущими открытыми дефектами.

Локальная приёмка использует только отдельные jazsem_rc_* PostgreSQL, приватный синтетический S3, настоящий Redis/Celery, fake SDK provider и SMTP sink. Пользовательские данные, платный AI и внешняя рассылка не используются. Production release не одобрен. Новые workflow ещё не запускались на GitHub: публикация ветки/PR требует отдельного разрешения.
