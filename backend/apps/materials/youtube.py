"""Accept video identities, never user-supplied iframe markup or embed hosts."""

import re
from urllib.parse import parse_qs, urlsplit

from rest_framework.exceptions import ValidationError

HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def video_id(value):
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
            raise ValueError()
        parts = url.path.strip("/").split("/")
        if url.hostname in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
            identity = parts[0]
        elif url.hostname in HOSTS:
            if parts == ["watch"]:
                values = parse_qs(url.query).get("v", [])
                if len(values) != 1:
                    raise ValueError()
                identity = values[0]
            elif len(parts) == 2 and parts[0] in {"embed", "shorts", "live", "v"}:
                identity = parts[1]
            else:
                raise ValueError()
        else:
            raise ValueError()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", identity):
            raise ValueError()
        return identity
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(
            {"external_url": "Добавьте корректную HTTPS-ссылку на видео YouTube."}
        ) from None


def normalize_youtube(value):
    return "https://www.youtube.com/watch?v=" + video_id(value)


def embed_url(value):
    return "https://www.youtube-nocookie.com/embed/" + video_id(value)
