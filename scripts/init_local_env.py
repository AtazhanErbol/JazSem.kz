"""Create a private development .env once, without printing or replacing secrets."""

import base64
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    database_password = secrets.token_hex(24)
    storage_password = secrets.token_hex(24)
    values = {
        "DJANGO_SECRET_KEY": secrets.token_hex(32),
        "POSTGRES_PASSWORD": database_password,
        "DATABASE_URL": f"postgresql://jazsem:{database_password}@postgres:5432/jazsem",
        "MINIO_ROOT_PASSWORD": storage_password,
        "S3_SECRET_KEY": storage_password,
        "MAIL_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "DEV_SEED_PASSWORD": secrets.token_urlsafe(24),
    }
    lines = []
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        lines.append(f"{key}={values[key]}" if key in values else line)
    try:
        with (root / ".env").open("x", encoding="utf-8", newline="\n") as target:
            target.write("\n".join(lines) + "\n")
    except FileExistsError:
        raise SystemExit("Existing .env preserved. Edit it locally if needed.") from None
    print("Created .env. Mail uses console; AI is disabled. Keep this file private.")


if __name__ == "__main__":
    main()
